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
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 날짜 범위 설정
start_date = datetime(2015, 1, 1)
end_date = datetime(2025, 3, 31)

today_str = datetime.now().strftime('%y%m%d')
filename = f'./data/fao_{end_date.strftime('%y%m%d')}.csv' # User's requested filename
keyword = 'coffee'

if os.path.exists(filename):
    print(f"[중단] {filename} 파일이 이미 존재합니다. 수집을 건너뜜니다.")
    exit()

# 크롬 드라이버 설정
chrome_options = Options()
chrome_options.add_argument('--headless')  # Run in headless mode
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage') # Overcome limited resource problems

driver = webdriver.Chrome(options=chrome_options)

article_data = []
visited_urls = set() 
page_num = 1

initial_url = f"https://www.fao.org/newsroom/search-result/{page_num}/en?indexCatalogue=search-index-newsroom&wordsMode=AllWords&fallbacklang=en&searchMode=all&contentTypes=FAONews.FaoNews&searchQuery={keyword}"
print(f"[진행상황] 초기 페이지 로드 중: {initial_url}")
driver.get(initial_url)
time.sleep(3)

while True:
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    search_results_holder = soup.find('div', id='search-results-holder')

    if not search_results_holder:
        print("[경고] 메인 검색 결과 컨테이너 (id='search-results-holder')를 찾지 못했습니다. 크롤링 종료.")
        break

    article_containers = search_results_holder.find_all('div', recursive=False)
    
    print(f"[디버깅] 페이지 {page_num}: 'search-results-holder' 아래 직접 div 컨테이너 총 {len(article_containers)}개 발견.")

    if not article_containers:
        print(f"[중단] 페이지 {page_num}: 'search-results-holder' 아래 기사 div를 찾지 못했습니다. 크롤링 종료.")
        break

    stop_crawling_by_date = False
    current_page_oldest_date = datetime.now()
    articles_found_on_page = 0

    for container_div in article_containers:
        title = None
        url = None
        date_str = None
        article_date = None

        try:
            content_info_divs = container_div.find_all('div', recursive=False)
            
            if len(content_info_divs) < 2:
                continue

            content_wrapper_div = content_info_divs[1]

            date_tag = content_wrapper_div.find('h6', class_='date')
            if not date_tag:
                 date_tag = content_wrapper_div.find('h6')
                 
            if date_tag:
                date_str = date_tag.text.strip()
                article_date = parse(date_str)
                
                if article_date < current_page_oldest_date:
                    current_page_oldest_date = article_date
            else:
                continue

            h5_tag = content_wrapper_div.find('h5', class_='title-link')
            if not h5_tag:
                h5_tag = content_wrapper_div.find('h5')

            a_tag = h5_tag.find('a') if h5_tag else None

            if a_tag and a_tag.has_attr('href'):
                title = a_tag.text.strip()
                relative_url = a_tag['href'].strip()
                if relative_url.startswith('/'):
                    url = "https://www.fao.org" + relative_url
                else:
                    url = relative_url
            else:
                continue

            if not (title and url and article_date):
                continue
            
            if start_date <= article_date <= end_date and url not in visited_urls:
                print(f"[수집] {article_date.strftime('%Y-%m-%d')} - {title}")
                article_data.append({
                    "date": article_date.strftime('%Y-%m-%d'),
                    "title": title,
                    "url": url
                })
                visited_urls.add(url)
                articles_found_on_page += 1 

        except Exception as e:
            print(f"[오류] 기사 파싱 중 일반 오류 발생 (페이지 {page_num}, 컨테이너 HTML:\n{container_div.prettify()[:500]}...): {e}")
            continue

    print(f"[페이지 {page_num}] 누적 수집 기사 수: {len(article_data)}개, 이번 페이지에서 {articles_found_on_page}개 수집.")

    if current_page_oldest_date < start_date:
        print(f"[중단] 현재 페이지의 가장 오래된 기사 날짜({current_page_oldest_date.date()})가 기준일({start_date.date()})보다 오래되었습니다. 수집을 종료합니다.")
        stop_crawling_by_date = True
    
    if articles_found_on_page == 0 and stop_crawling_by_date:
         print(f"[중단] 새 기사가 수집되지 않았고 기준일 이전 기사가 감지되어 수집 종료.")
         break
    
    page_num += 1 
    
    # 다음 페이지로 이동
    next_page_link_element = None
    try:
        next_page_links = driver.find_elements(By.XPATH, f"//ul[@class='pagination justify-content-center']//li/a[text()='{page_num}']")
        
        if next_page_links:
            next_page_link_element = next_page_links[0]
            print(f"[진행상황] 다음 페이지({page_num}) 버튼 클릭 시도.")
            driver.execute_script("arguments[0].click();", next_page_link_element)
            time.sleep(3) 
        else:
            print(f"[알림] 페이지 {page_num-1}: 다음 페이지({page_num}) 버튼을 찾을 수 없습니다. (pagination element not found or last page reached). 수집 종료.")
            break

    except Exception as e:
        print(f"[알림] 페이지 {page_num-1}: 다음 페이지 버튼 클릭 중 오류 발생. ({e}). 수집 종료.")
        break
    
    if stop_crawling_by_date:
        print(f"[중단] 날짜 기준에 도달하여 수집 종료.")
        break

driver.quit()

# 결과 저장
if article_data:
    os.makedirs('./data', exist_ok=True)
    df = pd.DataFrame(article_data)
    df.sort_values(by='date', ascending=False, inplace=True)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"[완료] 총 {len(df)}개의 기사를 '{filename}'에 저장했습니다.")
else:
    print("[경고] 수집된 기사가 없습니다. CSV 저장을 생략합니다.")