from boofilsic.settings import STAR_EMPTY, STAR_HALF, STAR_SOLID


def rating_to_emoji(score):
    """ convert score to mastodon star emoji code """
    if score is None or score == '' or score == 0:
        return ''
    solid_stars = score // 2
    half_star = int(bool(score % 2))
    empty_stars = 5 - solid_stars if not half_star else 5 - solid_stars - 1
    emoji_code = STAR_SOLID * solid_stars + STAR_HALF * half_star + STAR_SOLID * empty_stars
    return emoji_code