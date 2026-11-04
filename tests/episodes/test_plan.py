import pytest

from episodes.plan import (
    EpisodePlanError,
    cliffhanger_chapters,
    episode_of_chapter,
    plan_episodes,
)


def test_16_chuong_chia_5_6_5():
    eps = plan_episodes(16)
    assert [(e.first_chapter, e.last_chapter) for e in eps] == [(1, 5), (6, 11), (12, 16)]
    assert [e.number for e in eps] == [1, 2, 3]
    assert all(e.total == 3 for e in eps)
    assert eps[-1].is_last and not eps[0].is_last


def test_phan_du_don_vao_tap_giua_truoc_tap_dau_sau_cung():
    assert [(e.first_chapter, e.last_chapter) for e in plan_episodes(17)] == [(1, 5), (6, 11), (12, 17)]
    assert [(e.first_chapter, e.last_chapter) for e in plan_episodes(14)] == [(1, 4), (5, 9), (10, 14)]
    assert [(e.first_chapter, e.last_chapter) for e in plan_episodes(15)] == [(1, 5), (6, 10), (11, 15)]


def test_cac_tap_phu_kin_lien_tiep():
    for n in range(3, 25):
        eps = plan_episodes(n)
        assert eps[0].first_chapter == 1
        assert eps[-1].last_chapter == n
        for prev, curr in zip(eps, eps[1:]):
            assert curr.first_chapter == prev.last_chapter + 1


def test_cliffhanger_la_chuong_cuoi_cua_tap_1_va_2():
    assert cliffhanger_chapters(16) == [5, 11]


def test_episode_of_chapter():
    eps = plan_episodes(16)
    assert episode_of_chapter(1, eps).number == 1
    assert episode_of_chapter(11, eps).number == 2
    assert episode_of_chapter(12, eps).number == 3
    with pytest.raises(EpisodePlanError):
        episode_of_chapter(17, eps)


def test_it_chuong_hon_so_tap_thi_loi():
    with pytest.raises(EpisodePlanError):
        plan_episodes(2)


def test_label():
    assert plan_episodes(16)[1].label == "Tập 2/3"
