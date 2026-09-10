from mail_classifier import extract_folder


def test_extract_folder_from_same_line():
    response_text = "フォルダ候補：旅行"

    assert extract_folder(response_text) == "旅行"


def test_extract_folder_from_next_line():
    response_text = "フォルダ候補：\n旅行"

    assert extract_folder(response_text) == "旅行"


def test_extract_folder_returns_none_when_candidate_is_missing():
    response_text = "分類：旅行"

    assert extract_folder(response_text) is None


def test_extract_folder_returns_none_when_candidate_ends_the_response():
    assert extract_folder("フォルダ候補：") is None


def test_extract_folder_returns_none_when_candidate_is_blank():
    assert extract_folder("フォルダ候補：\n　") is None
