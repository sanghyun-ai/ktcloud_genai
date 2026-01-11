import os
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime

def get_youtube_trends(api_key, keyword, max_results=10):
    """
    특정 키워드로 유투브를 검색하여 영상 및 채널 정보를 가져옵니다.
    
    Args:
        api_key (str): YouTube Data API v3 Key
        keyword (str): 검색할 키워드
        max_results (int): 가져올 최대 영상 개수 (기본값: 10)
        
    Returns:
        pd.DataFrame: 검색 결과 데이터프레임
    """
    
    # YouTube API 서비스 빌드
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    print(f"'{keyword}' 키워드로 검색을 시작합니다...")
    
    # 1. 키워드 검색 (Search API)
    # search().list 비용: 100 quota
    search_response = youtube.search().list(
        q=keyword,
        part='snippet',
        type='video',
        maxResults=max_results,
        order='relevance' # 트렌드 파악을 위해 관련성 순, 혹은 date(최신순) 사용 가능
    ).execute()
    
    video_ids = []
    channel_ids = []
    items_data = []
    
    # 검색 결과에서 기본 정보 추출
    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        channel_id = item['snippet']['channelId']
        
        video_ids.append(video_id)
        channel_ids.append(channel_id)
        
        items_data.append({
            'video_id': video_id,
            'channel_id': channel_id,
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'published_at': item['snippet']['publishedAt'],
            'link': f"https://www.youtube.com/watch?v={video_id}"
        })
        
    if not video_ids:
        print("검색 결과가 없습니다.")
        return pd.DataFrame()

    # 2. 영상 상세 정보 조회 (조회수 등) - Videos API
    # videos().list 비용: 1 quota
    video_response = youtube.videos().list(
        part='statistics',
        id=','.join(video_ids)
    ).execute()
    
    video_stats = {}
    for item in video_response.get('items', []):
        stats = item.get('statistics', {})
        video_stats[item['id']] = {
            'view_count': stats.get('viewCount', 0)
        }
        
    # 3. 채널 상세 정보 조회 (구독자 수, 총 영상 수) - Channels API
    # channels().list 비용: 1 quota
    # 중복 채널 ID 제거하여 요청
    unique_channel_ids = list(set(channel_ids))
    channel_response = youtube.channels().list(
        part='statistics',
        id=','.join(unique_channel_ids)
    ).execute()
    
    channel_stats = {}
    for item in channel_response.get('items', []):
        stats = item.get('statistics', {})
        channel_stats[item['id']] = {
            'subscriber_count': stats.get('subscriberCount', 0),
            'total_video_count': stats.get('videoCount', 0)
        }
        
    # 4. 데이터 병합
    final_data = []
    for item in items_data:
        v_stat = video_stats.get(item['video_id'], {})
        c_stat = channel_stats.get(item['channel_id'], {})
        
        # 날짜 포맷 정리 (ISO 8601 -> YYYY-MM-DD)
        pub_date = item['published_at']
        try:
            dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            formatted_date = dt.strftime('%Y-%m-%d')
        except:
            formatted_date = pub_date

        row = {
            '썸네일': item['thumbnail'],
            '영상제목': item['title'],
            '링크': item['link'],
            '조회수': v_stat.get('view_count', 'N/A'),
            '구독자': c_stat.get('subscriber_count', 'N/A'),
            '총 영상수': c_stat.get('total_video_count', 'N/A'),
            '게시일': formatted_date
        }
        final_data.append(row)
        
    # 데이터프레임 생성
    df = pd.DataFrame(final_data)
    return df

# 사용 예시
if __name__ == "__main__":
    # 주의: 여기에 본인의 YouTube Data API 키를 입력해야 합니다.
    # API 키 발급 방법: Google Cloud Console -> 새 프로젝트 -> YouTube Data API v3 사용 설정 -> 사용자 인증 정보 만들기 (API 키)
    MY_API_KEY = "YOUR_API_KEY_HERE" 
    
    if MY_API_KEY == "YOUR_API_KEY_HERE":
        print("스크립트 내의 'MY_API_KEY' 변수에 유효한 YouTube API 키를 입력해주세요.")
    else:
        keyword = "AI 트렌드"
        df = get_youtube_trends(MY_API_KEY, keyword)
        
        if not df.empty:
            print(f"\n'{keyword}' 검색 결과:")
            # 출력 시 컬럼 순서 지정
            cols = ['영상제목', '조회수', '게시일', '구독자', '링크']
            print(df[cols].to_string(index=False))
            print("\n전체 데이터는 df 변수에 저장되었습니다.")
        
