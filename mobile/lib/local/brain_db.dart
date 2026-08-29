import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

/// Opens the on-device "Company Brain" SQLite database.
///
/// The database is shipped as a read-only Flutter asset at
/// `assets/brain.db`. sqflite (and the underlying platform SQLite APIs)
/// cannot open a file that lives inside the asset bundle directly, so on
/// first run the asset bytes are copied out to the app's documents
/// directory and opened from there. On later runs the copy is skipped if a
/// destination file already exists AND its `meta.built_at_utc` matches the
/// asset's, so a newer bundle (shipped in an app update) still replaces a
/// stale on-disk copy.
class BrainDb {
  final Database db;

  BrainDb._(this.db);

  static const String _assetPath = 'assets/brain.db';
  static const String _dbFileName = 'brain.db';

  /// Opens the database from the app documents directory, copying it out
  /// of the asset bundle first if necessary.
  static Future<BrainDb> openFromAsset() async {
    final docsDir = await getApplicationDocumentsDirectory();
    final destPath = p.join(docsDir.path, _dbFileName);

    final assetBytes = await rootBundle.load(_assetPath);
    final tempPath = p.join(docsDir.path, '$_dbFileName.from-asset.tmp');
    await _writeBytes(tempPath, assetBytes);

    String? assetBuiltAt;
    try {
      final tempDb = await openAt(tempPath);
      final tempMeta = await tempDb.meta();
      assetBuiltAt = tempMeta['built_at_utc'];
      await tempDb.close();
    } catch (_) {
      // If the temp copy can't be read for any reason, fall through and
      // treat it as "different from whatever is on disk" below.
      assetBuiltAt = null;
    }

    var shouldReplace = true;
    final destFile = File(destPath);
    if (await destFile.exists()) {
      try {
        final existingDb = await openAt(destPath);
        final existingMeta = await existingDb.meta();
        final existingBuiltAt = existingMeta['built_at_utc'];
        await existingDb.close();
        if (assetBuiltAt != null && assetBuiltAt == existingBuiltAt) {
          shouldReplace = false;
        }
      } catch (_) {
        // Existing file is unreadable/corrupt; replace it.
        shouldReplace = true;
      }
    }

    if (shouldReplace) {
      if (await destFile.exists()) {
        await destFile.delete();
      }
      await File(tempPath).copy(destPath);
    }

    // Clean up the temp copy either way.
    final tempFile = File(tempPath);
    if (await tempFile.exists()) {
      await tempFile.delete();
    }

    return openAt(destPath);
  }

  /// Opens an existing database file at [path] read-only. Used directly by
  /// tests, which build their own fixture database.
  static Future<BrainDb> openAt(String path) async {
    final db = await openDatabase(path, readOnly: true);
    return BrainDb._(db);
  }

  static Future<void> _writeBytes(String path, ByteData data) async {
    final file = File(path);
    final bytes = data.buffer.asUint8List(
      data.offsetInBytes,
      data.lengthInBytes,
    );
    await file.writeAsBytes(bytes, flush: true);
  }

  Future<Map<String, String>> meta() async {
    final rows = await db.query('meta');
    final result = <String, String>{};
    for (final row in rows) {
      result[row['key'] as String] = row['value'] as String;
    }
    return result;
  }

  Future<void> close() async {
    await db.close();
  }
}
