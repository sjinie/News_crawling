import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from dateutil.parser import parse
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

today_str = datetime.now().strftime('%y%m%d')
filename = f'./data/worldcoffeeportal_{today_str}.csv'

if os.path.exists(filename):
    print(f"[중단] 오늘({today_str}) 파일이 이미 존재합니다. 수집을 건너뜁니다.")
    exit()

start_date = datetime(2015, 1, 1)
end_date = datetime(2025, 3, 31)

# 크롬 드라이버 옵션 설정
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')

# 드라이버 실행
driver = webdriver.Chrome(options=chrome_options)
driver.get("https://www.worldcoffeeportal.com/news/")
time.sleep(3)

# 초기 변수
article_data = []
visited_urls = set()
page_count = 0
previous_card_count = 0  # 이전 페이지까지의 기사 수

while True:
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    grid = soup.find('div', class_='js-grid o-grid o-grid--4-columns')

    if not grid:
        print("[경고] 기사 그리드를 찾을 수 없습니다. 크롤링 종료.")
        break

    cards = grid.find_all('a', class_='c-card__link')
    current_card_count = len(cards)
    print(f"[디버깅] 페이지 {page_count + 1}: {current_card_count}개의 기사 카드 감지됨")

    # 기사 수 증가 없으면 중단
    if current_card_count <= previous_card_count:
        print(f"[중단] 기사 수가 더 이상 증가하지 않습니다. (이전: {previous_card_count}, 현재: {current_card_count})")
        break
    previous_card_count = current_card_count

    page_articles = []
    page_dates = []

    for card in cards:
        href = card.get('href')
        title = card.get_text(strip=True)
        full_url = "https://www.worldcoffeeportal.com" + href if href else None

        parent = card.find_parent('article')
        if not parent:
            continue

        time_tag = parent.find('time', class_='c-timestamp c-teaser__timestamp')
        if not time_tag or not time_tag.has_attr('datetime'):
            continue

        try:
            article_date = parse(time_tag['datetime'])  # 자동 포맷 인식
        except Exception as e:
            print(f"[오류] 날짜 파싱 실패: {e} / 값: {time_tag['datetime']}")
            continue

        page_dates.append(article_date)

        if start_date <= article_date <= end_date and full_url not in visited_urls:
            print(f"[수집] {article_date.strftime('%Y-%m-%d')} - {title}")
            page_articles.append({
                "date": article_date.strftime('%Y-%m-%d'),
                "title": title,
                "url": full_url
            })
            visited_urls.add(full_url)

    # 가장 오래된 날짜 출력
    if page_dates:
        oldest_in_page = min(page_dates)
        print(f"[진행상황] 페이지 {page_count + 1} 완료 - 가장 오래된 기사 날짜: {oldest_in_page.date()}")
        if oldest_in_page < start_date:
            print(f"[중단] 기사 날짜가 기준일({start_date.date()})보다 오래됨. 수집 종료.")
            break

    article_data.extend(page_articles)
    page_count += 1

    # 다음 페이지로 이동 (더보기 클릭)
    try:
        load_more_button = driver.find_element(By.CLASS_NAME, 'js-load-cards')
        driver.execute_script("arguments[0].click();", load_more_button)
        time.sleep(2)
    except Exception as e:
        print(f"[알림] 더 이상 '더보기' 버튼이 없습니다. 수집 종료. ({e})")
        break

driver.quit()

# 결과 저장
if article_data:
    os.makedirs('./data', exist_ok=True)
    df = pd.DataFrame(article_data)
    df.sort_values(by='date', ascending=False, inplace=True)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"[완료] 총 {len(df)}개의 기사를 'article_data.csv'에 저장했습니다.")
else:
    print("[경고] 수집된 기사가 없습니다. CSV 저장을 생략합니다.")
