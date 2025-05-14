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
filename = f'./data/dailycoffeenews_{today_str}.csv'

if os.path.exists(filename):
    print(f"[중단] 오늘({today_str}) 파일이 이미 존재합니다. 수집을 건너뜁니다.")
    exit()

# 날짜 범위 설정
start_date = datetime(2015, 1, 1)
end_date = datetime(2025, 3, 31)

# 크롬 드라이버 설정
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=chrome_options)

driver.get("https://dailycoffeenews.com/latest-news/")
time.sleep(3)

article_data = []
visited_urls = set()
page_count = 0

while True:
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    container = soup.find('div', class_='site-content-inner')  # 기사 영역

    if not container:
        print("[경고] 기사 컨테이너(site-content-inner)를 찾지 못했습니다.")
        break

    articles = container.find_all('article')
    if not articles:
        print("[경고] article 태그를 찾지 못했습니다.")
        break

    stop = False

    for article in articles:
        # 날짜 추출
        date_tag = article.find('p', class_='byline-date')
        if not date_tag:
            continue

        # 날짜만 추출 (예: 'April 16, 2025')
        match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', date_tag.text)
        if not match:
            print(f"[오류] 날짜 패턴을 찾지 못했습니다 / 원문: {date_tag.text.strip()}")
            continue

        date_str = match.group(1)

        try:
            article_date = datetime.strptime(date_str, '%B %d, %Y')
        except Exception as e:
            print(f"[오류] 날짜 파싱 실패: {e} / 값: {date_str}")
            continue

        if article_date < start_date:
            stop = True
            break
        if article_date > end_date:
            continue

        # 제목과 링크 추출
        h2_tag = article.find('h2')
        if not h2_tag:
            continue
        a_tag = h2_tag.find('a')
        if not a_tag or not a_tag.has_attr('href'):
            continue

        title = a_tag.text.strip()
        url = a_tag['href'].strip()

        if url not in visited_urls:
            article_data.append({
                'date': article_date.strftime('%Y-%m-%d'),
                'title': title,
                'url': url
            })
            visited_urls.add(url)

    print(f"[페이지 {page_count + 1}] 누적 수집 기사 수: {len(article_data)}개")
    page_count += 1

    if stop:
        print(f"[중단] 기준 날짜({start_date.date()}) 이전 기사가 감지되어 수집 종료.")
        break

    # 다음 페이지로 이동 (이전 뉴스 버튼)
    try:
        prev_button = driver.find_element(By.CSS_SELECTOR, 'div.pull-left a')
        driver.execute_script("arguments[0].click();", prev_button)
        time.sleep(2)
    except Exception as e:
        print(f"[알림] 더 이상 이전 페이지가 없습니다. ({e})")
        break

driver.quit()

# 결과 저장
if article_data:
    os.makedirs('./data', exist_ok=True)
    df = pd.DataFrame(article_data)
    df.sort_values(by='date', ascending=False, inplace=True)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"[완료] 총 {len(df)}개의 기사를 'dailycoffeenews_articles.csv'에 저장했습니다.")
else:
    print("[경고] 수집된 기사가 없습니다. CSV 저장 생략.")
