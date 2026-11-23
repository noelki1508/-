"""
블랙스톤 / 린치핀팀 일일 콘텐츠 생성기.
미술·시사·독서 콘텐츠에 린치핀팀·파이프라인 소득을 자연스럽게 연결.
"""
import json
import os
import random
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 콘텐츠 필러 (3가지 테마 × 3 타겟 페르소나 = 9 조합)
CONTENT_PILLARS = [
    {
        "pillar": "미술",
        "angle": "예술가의 태도에서 사업 인사이트 발견 — 함께하고 싶다는 감성 연결",
        "examples": ["모네의 집요함", "피카소의 관점 전환", "앤디 워홀의 대중화", "반 고흐의 뚝심"],
    },
    {
        "pillar": "시사",
        "angle": "대한민국 경제 현실(물가·실질임금·현금흐름 위기)에서 파이프라인 소득의 필요성",
        "examples": [
            "물가상승·실질임금 5년째 하락",
            "한국 가계부채 2000조 돌파",
            "청년 취업난·조기 퇴직 압박",
            "AI 시대 직업 대체 위기",
            "MZ 세대 N잡 트렌드 — 그래도 현금흐름은 안 나온다",
        ],
    },
    {
        "pillar": "독서",
        "angle": "린치핀(세스 고딘) 철학 + 현금흐름·파이프라인 관련 책으로 함께하고 싶은 팀 연결",
        "examples": [
            "린치핀 — 대체 불가능한 사람",
            "퍼플카우 — 눈에 띄어야 살아남는다",
            "부의 추월차선 — 시간 파는 구조의 한계와 현금흐름",
            "돈의 속성 — 현금흐름이 자유를 만든다",
        ],
    },
    {
        "pillar": "현금흐름",
        "angle": "대한민국 직장인·사업자 모두 현금흐름 없이는 진짜 자유 없다는 현실 직격",
        "examples": [
            "월급날만 기다리는 삶 vs 매일 들어오는 삶",
            "사장도 돈 없으면 직장인이다",
            "파이프라인 소득이 뭔지 모르는 한국인 90%",
            "자동화된 현금흐름 = 경제적 자유의 시작",
        ],
    },
]

PERSONAS = [
    {
        "name": "부업 직장인",
        "pain": "시간을 팔아도 통장은 그대로",
        "desire": "퇴근 후에도 돌아가는 수익 구조",
    },
    {
        "name": "편견 있는 탐색자",
        "pain": "네트워크 마케팅 편견, 그래도 무언가 찾는 중",
        "desire": "진짜 검증된 65년 된 사업 모델",
    },
    {
        "name": "경제적 자유 추구자",
        "pain": "어디서 시작해야 할지 모름",
        "desire": "자는 동안에도 수익이 들어오는 파이프라인",
    },
]

SYSTEM_PROMPT = """
당신은 @blk_writer 계정(블랙스톤·린치핀팀)의 Threads 콘텐츠 전략가입니다.

[브랜드 아이덴티티]
- 계정명: @blk_writer · 블랙스톤
- 팀명: 린치핀팀 (세스 고딘 린치핀 철학 기반)
- 운영자: 폐기물 수집·운반업 대표 10년+ (환경 사업 대표)
- 핵심 가치: 믿음·관계·사랑으로 팀 만들기
- 목표: 파이프라인 소득을 함께 만들 열정적인 파트너 모집

[글쓰기 원칙]
- 반말체 (해, 야, 거야, 있어)
- 직접 판매 금지 — 가치 먼저, 관계 먼저
- 미술·시사·독서 인사이트 → 자연스럽게 린치핀팀 연결
- 암웨이 직접 언급 절대 금지 (린치핀팀 / 블랙스톤만)
- 세스 고딘 린치핀 철학 반영: "대체 불가능한 사람", "진짜 연결이 가치를 만든다"
- 텍스트 포스트: 100-180자, 줄바꿈 활용, 마지막에 DM 유도

[포스트 구조]
훅 (1-2줄) → 인사이트/공감 (2-3줄) → 린치핀팀 연결 (1-2줄) → CTA (1줄)
"""

SLIDE_SCHEMA = """
Return ONLY valid JSON (no markdown, no explanation):
{
  "text_post": "Threads 텍스트 포스트 (반말, 100-180자, 줄바꿈 \\n 사용)",
  "caption": "이미지 게시 캡션 1-2줄",
  "slides": [
    {"tag": "훅 태그", "main": "메인 텍스트 (짧게)", "sub": "서브 설명", "type": "hook"},
    {"tag": "태그", "main": "공감 텍스트", "sub": "설명", "type": "pain"},
    {"tag": "태그", "main": "인사이트", "quote": "인용구", "source": "출처", "type": "quote"},
    {"tag": "태그", "main": "결과", "stats": [{"num": "숫자/단어", "label": "설명"}], "type": "stats"},
    {"tag": "린치핀팀", "main": "희소성", "sub": "자격 필터", "urgent": "긴급 메시지", "type": "scarcity"},
    {"tag": "행동", "main": "CTA", "sub": "설명", "type": "cta"}
  ]
}
"""


def generate_content(pillar: str = None, persona: dict = None) -> dict:
    if not ANTHROPIC_API_KEY:
        return _fallback_content()

    import anthropic

    chosen_pillar = next(
        (p for p in CONTENT_PILLARS if p["pillar"] == pillar), None
    ) or random.choice(CONTENT_PILLARS)

    if not persona:
        persona = random.choice(PERSONAS)

    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().weekday()  # 0=월요일

    user_prompt = f"""
오늘({today}) 블랙스톤 · 린치핀팀 Threads 콘텐츠를 만들어.

[콘텐츠 필러]
테마: {chosen_pillar['pillar']}
방향: {chosen_pillar['angle']}
예시 소재: {', '.join(chosen_pillar['examples'])}

[타겟 페르소나]
{persona['name']}
- 아픔: {persona['pain']}
- 욕망: {persona['desire']}

[주의]
- 미술/시사/독서 이야기를 먼저 충분히 하고, 자연스럽게 린치핀팀·파이프라인 소득으로 연결
- 판매보다 공감과 인사이트 중심
- "린치핀팀" 단어는 1회만 사용

{SLIDE_SCHEMA}
"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-5",
        max_tokens=1800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = msg.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


def get_todays_pillar() -> str:
    """요일별 테마 순환: 월=현금흐름, 화=시사, 수=독서, 목=미술, 금=현금흐름, 토=시사, 일=독서"""
    day = datetime.now().weekday()
    rotation = ["현금흐름", "시사", "독서", "미술", "현금흐름", "시사", "독서"]
    return rotation[day]


def _fallback_content() -> dict:
    templates = [
        {
            "text_post": "모네는 같은 풍경을 100번 넘게 그렸어.\n빛이 달라질 때마다 다시 봤거든.\n\n대부분은 한 번 보고 '알겠어' 하고 넘겨.\n근데 진짜 가치는 반복에서 나오더라.\n\n나도 그렇게 사업 10년 하다가 린치핀팀 만들었어.\n파이프라인 소득 궁금하면 DM 줘.",
            "caption": "모네처럼 집요하게 — 린치핀팀이 만드는 파이프라인 👆",
            "slides": [
                {"tag": "미술 인사이트", "main": "모네는 같은 풍경을\n100번 넘게 그렸어.", "sub": "빛이 달라질 때마다 다시 봤거든.", "type": "hook"},
                {"tag": "현실", "main": "대부분은 한 번 보고\n'알겠어' 하고 넘겨.", "sub": "근데 진짜 가치는 반복과 집요함에서 나온다.", "type": "pain"},
                {"tag": "세스 고딘", "main": "린치핀은 그런 사람이야.", "quote": "\"대체 불가능한 사람이 돼라.\n평범한 건 이제 안전하지 않다.\"", "source": "— Seth Godin, Linchpin", "type": "quote"},
                {"tag": "지금은", "main": "자는 동안에도\n수익이 들어오는\n구조 만들었어.", "stats": [{"num": "10년+", "label": "사업 경력"}, {"num": "24/7", "label": "수익 구조"}, {"num": "팀", "label": "함께 성장"}], "type": "stats"},
                {"tag": "린치핀팀", "main": "아무나\n안 받아.", "sub": "빠른 돈 원하는 사람 말고\n열정적으로 함께 할 사람만.", "urgent": "이번 달 파트너 딱 2명만 더 받아.", "type": "scarcity"},
                {"tag": "함께 할 사람", "main": "궁금하면\n일단 DM만 줘.", "sub": "24시간 안에 직접 설명해줄게.\n강매 없어. 판단은 네가 해.", "type": "cta"},
            ],
        },
        {
            "text_post": "요즘 실질임금 계속 떨어지고 있어.\n물가는 오르는데 월급은 그대로야.\n\n직장인 10명 중 6명이 N잡 뛰는데\n대부분은 시간을 더 파는 거야.\n구조가 바뀐 게 아니야.\n\n파이프라인 소득 궁금하면 DM 줘.",
            "caption": "시간 파는 N잡 말고, 구조를 바꾸는 린치핀팀 👆",
            "slides": [
                {"tag": "시사", "main": "실질임금이\n계속 떨어지고 있어.", "sub": "물가는 오르는데 월급은 그대로야.", "type": "hook"},
                {"tag": "현실", "main": "직장인 10명 중\n6명이 N잡 뛴다.", "sub": "근데 대부분은 시간을 더 파는 거야.\n구조가 바뀐 게 아니야.", "type": "pain"},
                {"tag": "전환점", "main": "진짜 자유는\n구조에서 나와.", "quote": "\"돈이 일하게 해야 한다.\n내가 일할 필요 없이.\"", "source": "— 부의 추월차선", "type": "quote"},
                {"tag": "지금은", "main": "내가 자도\n돈이 들어오는\n구조 만들었어.", "stats": [{"num": "자동", "label": "24시간 수익"}, {"num": "팀", "label": "함께 성장"}, {"num": "10년", "label": "검증된 시스템"}], "type": "stats"},
                {"tag": "린치핀팀", "main": "믿음·관계·사랑으로\n팀 만드는 중이야.", "sub": "빠른 수익 아니야.\n열정적으로 함께 할 사람 찾아.", "urgent": "이번 달 자리 딱 2명 남았어.", "type": "scarcity"},
                {"tag": "같이 할 사람", "main": "조건 없이\n얘기 먼저 해보자.", "sub": "24시간 안에 답장 줄게.\n강매 없어.", "type": "cta"},
            ],
        },
        {
            "text_post": "린치핀 읽었어?\n세스 고딘이 말해.\n'평범함은 이제 안전하지 않다'고.\n\n직장에서도 사업에서도\n대체 가능한 사람은 결국 대체돼.\n\n나는 대체 불가능한 구조를 만들기로 했어.\n린치핀팀 얘기 들어볼래? DM 줘.",
            "caption": "린치핀 — 대체 불가능한 사람이 되는 법 👆",
            "slides": [
                {"tag": "독서", "main": "린치핀.\n세스 고딘의 책이야.", "sub": "\"평범함은 이제 안전하지 않다.\"", "type": "hook"},
                {"tag": "현실", "main": "대체 가능한 사람은\n결국 대체돼.", "sub": "직장에서도 사업에서도 마찬가지야.", "type": "pain"},
                {"tag": "세스 고딘", "main": "그래서 린치핀이\n필요해.", "quote": "\"진짜 연결이 가치를 만든다.\n예술가처럼 일해라.\"", "source": "— Seth Godin, Linchpin", "type": "quote"},
                {"tag": "지금은", "main": "나는 대체 불가능한\n구조를 만들었어.", "stats": [{"num": "10년+", "label": "환경 사업"}, {"num": "24/7", "label": "파이프라인 수익"}, {"num": "팀", "label": "린치핀팀"}], "type": "stats"},
                {"tag": "린치핀팀", "main": "아무나\n안 받아.", "sub": "빠른 돈보다\n진짜 연결을 원하는 사람만.", "urgent": "이번 달 파트너 딱 2명 남아.", "type": "scarcity"},
                {"tag": "함께 할 사람", "main": "열정적으로\n같이 하고 싶으면 DM 줘.", "sub": "24시간 안에 직접 설명해줄게.\n강매 없어.", "type": "cta"},
            ],
        },
    ]
    return random.choice(templates)
