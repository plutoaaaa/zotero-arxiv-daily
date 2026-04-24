from .protocol import Paper
import math


def _is_chinese_language(language: str | None) -> bool:
    normalized = str(language or '').lower()
    return 'chinese' in normalized or '中文' in normalized


def _get_strings(language: str | None) -> dict[str, str]:
    if _is_chinese_language(language):
        return {
            'footer': '如需取消订阅，请在 GitHub Actions 设置中移除收件邮箱。',
            'empty': '今天没有匹配论文，先休息一下。',
            'relevance': '相关度',
            'tldr': '摘要',
            'pdf': 'PDF',
            'unknown_score': '未知',
        }
    return {
        'footer': 'To unsubscribe, remove your email in your Github Action setting.',
        'empty': 'No Papers Today. Take a Rest!',
        'relevance': 'Relevance',
        'tldr': 'TLDR',
        'pdf': 'PDF',
        'unknown_score': 'Unknown',
    }


def get_framework(footer: str) -> str:
    return f"""
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {{
      font-size: 1.3em;
      line-height: 1;
      display: inline-flex;
      align-items: center;
    }}
    .half-star {{
      display: inline-block;
      width: 0.5em;
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }}
    .full-star {{
      vertical-align: middle;
    }}
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
{footer}
</div>

</body>
</html>
"""


def get_empty_html(empty_text: str | None = None):
    strings = _get_strings('Chinese') if empty_text and '今天' in empty_text else _get_strings('English')
    text = empty_text or strings['empty']
    block_template = f"""
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        {text}
    </td>
  </tr>
  </table>
  """
    return block_template


def get_block_html(title:str, authors:str, rate:str, tldr:str, pdf_url:str, affiliations:str | None = None, strings: dict[str, str] | None = None):
    strings = strings or _get_strings('English')
    affiliation_html = ''
    if affiliations:
        affiliation_html = f"""
            <br>
            <i>{affiliations}</i>
        """
    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            {affiliation_html}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>{relevance_label}:</strong> {rate}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>{tldr_label}:</strong> {tldr}
        </td>
    </tr>

    <tr>
        <td style="padding: 8px 0;">
            <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">{pdf_label}</a>
        </td>
    </tr>
</table>
"""
    return block_template.format(
        title=title,
        authors=authors,
        rate=rate,
        tldr=tldr,
        pdf_url=pdf_url,
        affiliation_html=affiliation_html,
        relevance_label=strings['relevance'],
        tldr_label=strings['tldr'],
        pdf_label=strings['pdf'],
    )


def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(papers:list[Paper], language: str = 'English') -> str:
    strings = _get_strings(language)
    framework = get_framework(strings['footer'])
    parts = []
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html(strings['empty']))
    
    for p in papers:
        rate = round(p.score, 1) if p.score is not None else strings['unknown_score']
        author_list = [a for a in p.authors]
        num_authors = len(author_list)
        if num_authors <= 5:
            authors = ', '.join(author_list)
        else:
            authors = ', '.join(author_list[:3] + ['...'] + author_list[-2:])
        affiliations = None
        if p.affiliations is not None:
            affiliations = p.affiliations[:5]
            affiliations = ', '.join(affiliations)
            if len(p.affiliations) > 5:
                affiliations += ', ...'
        parts.append(get_block_html(p.title, authors, rate, p.tldr or '', p.pdf_url or p.url, affiliations, strings))

    content = '<br>' + '</br><br>'.join(parts) + '</br>'
    return framework.replace('__CONTENT__', content)