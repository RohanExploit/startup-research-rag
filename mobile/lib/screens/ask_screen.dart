import 'package:flutter/material.dart';

import '../llm/llm_service.dart';
import '../llm/prompt_builder.dart';
import '../local/brain_db.dart';
import '../local/local_retriever.dart';
import '../local/models.dart';

/// The three states the ask screen can be in before it's ready to answer
/// questions.
enum _SetupState { checking, missing, ready }

/// Top-level screen: types a question, gets an answer, entirely on-device.
///
/// On launch it checks both [BrainDb.isAvailable] and
/// [LlmService.isModelPresent]. If either is missing it shows a setup
/// screen naming exactly what's absent and how to fix it -- never a crash,
/// never an empty chat pretending everything is fine.
class AskScreen extends StatefulWidget {
  const AskScreen({super.key});

  @override
  State<AskScreen> createState() => _AskScreenState();
}

class _AnsweredTurn {
  final String question;
  final RetrievalResult retrieval;
  String answer;
  bool streaming;
  final Stopwatch stopwatch;
  int tokenCount;

  _AnsweredTurn({
    required this.question,
    required this.retrieval,
    this.answer = '',
    this.streaming = true,
  })  : stopwatch = Stopwatch()..start(),
        tokenCount = 0;

  double get elapsedSeconds => stopwatch.elapsedMilliseconds / 1000.0;

  double get tokensPerSecond {
    final seconds = elapsedSeconds;
    if (seconds <= 0) return 0;
    return tokenCount / seconds;
  }
}

class _AskScreenState extends State<AskScreen> {
  _SetupState _setupState = _SetupState.checking;
  bool _dbMissing = false;
  bool _modelMissing = false;
  String? _modelMissingMessage;

  BrainDb? _brainDb;
  LocalRetriever? _retriever;
  final LlmService _llmService = LlmService();

  final TextEditingController _controller = TextEditingController();
  final List<_AnsweredTurn> _turns = [];
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _runSetupCheck();
  }

  Future<void> _runSetupCheck() async {
    // Guarded broadly (not just the documented exception types): on a
    // platform with no path_provider channel at all -- a plain
    // `flutter test` run with no device -- these calls can throw rather
    // than resolve false. Either way the correct behaviour is the same
    // setup screen, never an unhandled exception.
    bool dbAvailable;
    bool modelPresent;
    try {
      dbAvailable = await BrainDb.isAvailable();
    } catch (_) {
      dbAvailable = false;
    }
    try {
      modelPresent = await LlmService.isModelPresent();
    } catch (_) {
      modelPresent = false;
    }

    if (!dbAvailable || !modelPresent) {
      if (!mounted) return;
      setState(() {
        _dbMissing = !dbAvailable;
        _modelMissing = !modelPresent;
        _setupState = _SetupState.missing;
      });
      return;
    }

    try {
      final db = await BrainDb.open();
      await _llmService.initialize();
      if (!mounted) return;
      setState(() {
        _brainDb = db;
        _retriever = LocalRetriever(db);
        _setupState = _SetupState.ready;
      });
    } on BrainDbMissingException {
      if (!mounted) return;
      setState(() {
        _dbMissing = true;
        _setupState = _SetupState.missing;
      });
    } on ModelMissingException catch (e) {
      if (!mounted) return;
      setState(() {
        _modelMissing = true;
        _modelMissingMessage = e.message;
        _setupState = _SetupState.missing;
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _llmService.dispose();
    _brainDb?.close();
    super.dispose();
  }

  Future<void> _submit() async {
    final question = _controller.text.trim();
    final retriever = _retriever;
    if (question.isEmpty || retriever == null || _busy) return;

    _controller.clear();
    setState(() => _busy = true);

    final retrieval = await retriever.retrieve(question);
    final turn = _AnsweredTurn(question: question, retrieval: retrieval);
    setState(() => _turns.insert(0, turn));

    if (retrieval.route == 'TABULAR') {
      // Exact SQL answer -- shown verbatim, no model call. See
      // prompt_builder.dart's contract note on TABULAR routes.
      turn.answer = retrieval.context;
      turn.tokenCount = retrieval.context.split(RegExp(r'\s+')).length;
      turn.streaming = false;
      turn.stopwatch.stop();
      setState(() => _busy = false);
      return;
    }

    final prompt = buildPrompt(question: question, retrieval: retrieval);
    try {
      await for (final token in _llmService.generateStream(prompt)) {
        turn.answer += token;
        turn.tokenCount += 1;
        if (mounted) setState(() {});
      }
    } catch (e) {
      turn.answer = turn.answer.isEmpty ? 'Generation failed: $e' : turn.answer;
    } finally {
      turn.streaming = false;
      turn.stopwatch.stop();
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Company Brain')),
      body: switch (_setupState) {
        _SetupState.checking => const _CheckingView(),
        _SetupState.missing => _SetupMissingView(
            dbMissing: _dbMissing,
            modelMissing: _modelMissing,
            modelMissingMessage: _modelMissingMessage,
            onRetry: () {
              setState(() => _setupState = _SetupState.checking);
              _runSetupCheck();
            },
          ),
        _SetupState.ready => _ChatView(
            controller: _controller,
            turns: _turns,
            busy: _busy,
            onSubmit: _submit,
          ),
      },
    );
  }
}

class _CheckingView extends StatelessWidget {
  const _CheckingView({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: CircularProgressIndicator());
  }
}

class _SetupMissingView extends StatelessWidget {
  final bool dbMissing;
  final bool modelMissing;
  final String? modelMissingMessage;
  final VoidCallback onRetry;

  const _SetupMissingView({
    super.key,
    required this.dbMissing,
    required this.modelMissing,
    required this.modelMissingMessage,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.warning_amber_rounded, size: 48, color: Colors.amber),
            const SizedBox(height: 16),
            Text(
              'Setup incomplete',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            if (dbMissing)
              const _MissingItem(
                title: 'Database missing',
                detail:
                    'brain.db was not found. Push it with:\n'
                    'adb push brain.db '
                    '/sdcard/Android/data/com.companybrain.company_brain/files/brain.db',
              ),
            if (dbMissing && modelMissing) const SizedBox(height: 20),
            if (modelMissing)
              _MissingItem(
                title: 'Model missing',
                detail: modelMissingMessage ??
                    'The on-device model (${LlmService.modelFileName}) was not found.',
              ),
            const SizedBox(height: 24),
            FilledButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _MissingItem extends StatelessWidget {
  final String title;
  final String detail;

  const _MissingItem({super.key, required this.title, required this.detail});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 4),
        SelectableText(
          detail,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
        ),
      ],
    );
  }
}

class _ChatView extends StatelessWidget {
  final TextEditingController controller;
  final List<_AnsweredTurn> turns;
  final bool busy;
  final VoidCallback onSubmit;

  const _ChatView({
    super.key,
    required this.controller,
    required this.turns,
    required this.busy,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: turns.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      'Ask a question. Everything runs on this phone -- '
                      'no network, no server.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              : ListView.builder(
                  reverse: true,
                  padding: const EdgeInsets.all(12),
                  itemCount: turns.length,
                  itemBuilder: (context, index) => _TurnCard(turn: turns[index]),
                ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: controller,
                    enabled: !busy,
                    decoration: const InputDecoration(
                      hintText: 'Ask a question…',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => onSubmit(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: busy ? null : onSubmit,
                  icon: busy
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _TurnCard extends StatelessWidget {
  final _AnsweredTurn turn;

  const _TurnCard({super.key, required this.turn});

  Color _routeColor(BuildContext context) {
    switch (turn.retrieval.route) {
      case 'TABULAR':
        return Colors.teal;
      case 'FACT':
        return Colors.indigo;
      case 'LOCAL':
        return Colors.deepPurple;
      case 'GLOBAL':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final sources = turn.retrieval.sources;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(turn.question, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Row(
              children: [
                Chip(
                  label: Text(turn.retrieval.route),
                  backgroundColor: _routeColor(context).withValues(alpha: 0.25),
                  labelStyle: TextStyle(color: _routeColor(context)),
                  visualDensity: VisualDensity.compact,
                ),
                const Spacer(),
                if (turn.streaming)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            SelectableText(turn.answer.isEmpty ? '…' : turn.answer),
            const SizedBox(height: 8),
            Text(
              '${turn.elapsedSeconds.toStringAsFixed(1)}s'
              '${turn.retrieval.route == 'TABULAR' ? '' : ' · ${turn.tokensPerSecond.toStringAsFixed(1)} tok/s'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (sources.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Sources', style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 4),
              ...sources.map(
                (s) => Text(
                  '• ${s.docId}${s.section != null ? ' — ${s.section}' : ''}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
