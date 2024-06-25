from PyPDF2 import PdfReader
from collections import namedtuple
import re
import sys


regex_patterns_to_remove = [
    r"This electronic transcript is a certified, authentic University of Tasmania document when viewed within \
    the My eQuals portal and is valid at the time of issue .\n",
    r"The University of Tasmania cannot verify this document 's authenticity in printed format.",
    r'Page \d of 5',
    r'UNIVERSITY OF TASMANIA',
    r'Academic Transcript',
    r'As At : 11/12/2020',
    r'Student:    \d{6}    [\w ]+ Date of Birth: \d{2]/\d{2]/\d{4]',
    r'Credit Points Grade Mark',
]

pass_fail_grade_symbols = [
    'HD',
    'DN',
    'CR',
    'PP',
    'UP',
    'TP',
]

other_grade_symbols = [
    'XE',
]

withdrawn_grade_symbols = [
    'WW',
    'WN',
]

all_grade_symbols = pass_fail_grade_symbols + other_grade_symbols + withdrawn_grade_symbols

Unit = namedtuple("Unit", ["code", "name", "mark", "grade", "credit_points", "degree", "semester", "year"])


def does_line_end_with_unit_code(line: str):
    if re.search(r"[A-Z]{3}\d{3}$", line) is not None:
        return True
    return False


def is_unit_line(line: str):
    return any([line.startswith(symbol) for symbol in all_grade_symbols])


def is_unit_line_broken(line: str):
    return not does_line_end_with_unit_code(line)


def does_start_with_year(s: str):
    return re.match(r"2\d{3}", s)


def is_start_of_semester_block(s: str):
    semester_block_indicators = [
        "Semester",
        "Winter",
        "Spring",
        "Summer",
    ]
    return any([s.startswith(x) for x in semester_block_indicators])


def remove_patterns(text: str, patterns: list):
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return text


# def alternative_2_process_unit_line(line:str, degree, year:str, semester:str, ) -> Unit:
#     grade, line = line.split(" ", 1)
#     mark, line = line.split(" ", 1)


def alternative_1_process_unit_line(line: str, degree, year: str, semester: str, ) -> Unit:
    unit_code_regex = r"([A-Z]{3}\d{3})$"
    try:
        unit_code = re.search(unit_code_regex, line).group(0)
    except AttributeError:
        print(f"Failed to match unit code in line: {line}")
        return Unit(None, line, None, None, None, degree=degree, semester=semester, year=year)
    line = line.replace(unit_code, "").strip()
    grade, line = line.split(" ", 1)
    unit_name = line.strip()
    return Unit(unit_code, unit_name, None, grade, None, degree, semester, year)


def is_python_less_than_3_11():
    return sys.version_info < (3, 11)


def process_unit_line(line: str, degree, year: str, semester: str, ) -> Unit:
    """tbh, I probably should have extracted a bit of data WITHOUT regex to reduce the line a bit first.
    # grade, remainder = line.split(" ", 1)
    # mark, remainder = remainder.split(" ", 1)
    """

    if is_python_less_than_3_11():
        regex_pattern = r"([A-Z]{2}) ((\d{2} )|)(.+) (\d+(\.\d)?) +([A-Z]{3}\d{3})"
        re_group_map = {
            "grade": 1,
            "mark": 2,
            "unit_name": 4,
            "credit_points": 5,
            "unit_code": 7,
        }
    else:
        regex_pattern = r"([A-Z]{2}) ((?>\d{2} )|)(.+) (\d+(?>\.\d)?) +([A-Z]{3}\d{3})"
        re_group_map = {
            "grade": 1,
            "mark": 2,
            "unit_name": 3,
            "credit_points": 4,
            "unit_code": 5,
        }
        
    # Modified to work with python 3.10 (above works with 3.11 and above). i.e. '?>' is not supported in 3.10
    match_obj = re.match(regex_pattern, line)
    if not match_obj:
        return alternative_1_process_unit_line(line, degree, year, semester, )
    grade = match_obj[re_group_map["grade"]].strip()
    mark = match_obj[re_group_map["mark"]].strip()
    unit_name = match_obj[re_group_map["unit_name"]].strip()
    credit_points = match_obj[re_group_map["credit_points"]].strip()
    unit_code = match_obj[re_group_map["unit_code"]].strip()
    return Unit(unit_code, unit_name, mark, grade, credit_points, degree, semester, year)


def process_semester_block(lines, year: str, degree: str, ) -> list[Unit]:
    units_accumulator: list[Unit] = []
    semester = lines[0]
    # print(f"Semester: {semester}")
    for i in range(1, len(lines)):
        line = lines[i]
        if not is_unit_line(line):
            break
        if is_unit_line_broken(line):
            # print(f"Broken line: {line}")
            line = line + lines[i + 1]
            i += 1
        units_accumulator.append(process_unit_line(line, degree, year, semester, ))
    return units_accumulator


def process_year_degree_block(lines):
    """Pattern is
        <Year> <Degree>
        <Semester X>
        <Grade> <Mark> <Unit Name> <Credit Points> <Unit Code>
        ...
        <Grade> <Mark> <Unit Name> <Credit Points> <Unit Code>
        <Semester Y>
        <Year> <Degree>
        ...
        """

    units_accumulator = []

    # Assume first line is year degree
    year, degree = lines[0].split("    ", 1)
    # Semesters follow
    for i in range(1, len(lines)):
        line = lines[i]
        # if line is semester block start
        if is_start_of_semester_block(line):
            units_accumulator.extend(process_semester_block(lines[i:], year, degree))
        if does_start_with_year(line):
            break
    return units_accumulator


def join_pages(pdf_reader: PdfReader):
    pages = pdf_reader.pages
    text = ""
    for page in pages:
        text += page.extract_text()
    return text


def extract_page_data(pdf_file) -> list[Unit]:
    reader = PdfReader(pdf_file)
    text = join_pages(reader)

    unit_accumulator = []
    text = remove_patterns(text, regex_patterns_to_remove)

    lines = [line.strip() for line in text.split("\n")]

    year_block_start_lines = []
    for i in range(len(lines)):
        line = lines[i]
        if does_start_with_year(line):
            year_block_start_lines.append(i)

    for j in year_block_start_lines:
        unit_accumulator.extend(process_year_degree_block(lines[j:]))
    return unit_accumulator
