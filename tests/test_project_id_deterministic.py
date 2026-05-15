from scripts.utils_project_id import canonicalize_url, generate_project_id

def test_project_id_deterministic_and_url_normalized():
    u1='https://www.jica.go.jp/detail/1.html?utm=abc#top'
    u2='https://www.jica.go.jp/detail/1.html'
    assert canonicalize_url(u1)==canonicalize_url(u2)
    a=generate_project_id('Kenya','Project A','無償資金協力',u1)
    b=generate_project_id('Kenya','Project A','無償資金協力',u2)
    assert a==b
