from audit_shm_links import norm, signa
from rebuild_verified_shm_links import matching_owners, host_is_shm


def page(value, title='Runsten'):
    return f'<meta property="og:title" content="{title}"><table><tr><th>Andra nummer</th><td>{value}</td></tr></table>'


def test_signum_in_plain_field_and_list():
    assert signa(page('Runsignum: U 82')) == ['U 82']
    assert signa(page('<ul><li>Undernummer: 2</li><li>Runsignum: Öl Fv1911;274B</li></ul>')) == ['Öl Fv1911;274B']
    assert signa(page('Runsignum: Vg 279 Undernummer: 73:G1 1961')) == ['Vg 279']
    assert signa(page('Runsignum: U 9 Runsignum: U 8')) == ['U 9', 'U 8']


def test_identity_is_exact_and_alternatives_are_explicit():
    owners={norm('U 82'):{82},norm('U 83'):{83},norm('Ög KJ59'):{178}}
    assert matching_owners(page('Runsignum: U 83'),owners)[0] == {83}
    assert matching_owners(page('Runsignum: U 820'),owners)[0] == set()
    assert matching_owners(page('Runsignum: Ög KJ59'),owners)[0] == {178}
    assert matching_owners(page('Runsignum: U 8'),owners)[0] == set()


def test_title_does_not_override_conflicting_signum():
    owners={norm('U 82'):{82},norm('U 83'):{83}}
    assert matching_owners(page('',title='U 82'),owners) == ({82},'exact_title')
    assert matching_owners(page('Runsignum: U 83',title='U 82'),owners)[0] == set()
    assert matching_owners(page('',title='U 82 and U 83'),owners)[0] == set()
    assert matching_owners(page('Runsignum: U 82'),{norm('U 82'):{1,2}})[0] == set()


def test_shm_host_is_not_matched_by_path_or_substring():
    assert host_is_shm('https://media.samlingar.shm.se/item/test')
    assert not host_is_shm('https://shm.se.example.org/test')
    assert not host_is_shm('https://example.org/shm.se/test')


def test_test_records_are_excluded_even_when_the_signum_matches():
    assert matching_owners(page("Runsignum: U 109",title="Testpost 1"),{norm("U 109"):{109}})[0] == set()
