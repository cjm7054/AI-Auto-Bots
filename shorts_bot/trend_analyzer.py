import datetime
try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None

def get_daily_trends(country='south_korea'):
    """
    구글 트렌드를 활용하여 오늘의 실시간 인기 검색어 상위 3개를 가져옵니다.
    네트워크 문제나 라이브러리 미설치 시 기본 키워드를 반환합니다.
    """
    if not TrendReq:
        return ["AI 자동화 부업", "챗GPT 수익화", "무자본 창업"]
        
    try:
        pytrend = TrendReq(hl='ko-KR', tz=540) # 한국 시간대
        trending_searches_df = pytrend.trending_searches(pn=country)
        
        # 상위 3개 키워드 추출
        top_trends = trending_searches_df.head(3)[0].tolist()
        return top_trends
    except Exception as e:
        print(f"[TrendAnalyzer] 트렌드 수집 실패, 기본값 대체: {e}")
        return ["최신 AI 부업 트렌드", "초보자 숏폼 떡상", "유튜브 자동화 수익"]

if __name__ == "__main__":
    trends = get_daily_trends()
    print(f"오늘의 핫이슈 키워드: {trends}")
