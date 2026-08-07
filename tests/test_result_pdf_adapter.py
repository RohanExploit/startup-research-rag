import pytest
from models.canonical import StudentRecord
from adapters.result_pdf_adapter import load_student_record

def test_load_student_record_valid():
    tenant_id = "tenant_1"
    roll_no = "2267571242025"
    
    student = load_student_record(tenant_id, roll_no)
    
    assert isinstance(student, StudentRecord)
    assert student.roll_no == "2267571242025"
    assert student.sgpa is not None
    assert len(student.subjects) > 0
    
    # Check shape of subject
    subject = student.subjects[0]
    assert hasattr(subject, "code")
    assert hasattr(subject, "credit")
    assert hasattr(subject, "grade_point")
