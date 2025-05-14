import os
import pandas as pd
import glob
import re
from datetime import datetime

# === 1. 최신 기사 파일 불러오기 ===
def get_latest_article_file():
    csv_files = glob.glob('./data/worldcoffeeportal_*.csv')
    if not csv_files:
        raise FileNotFoundError("기사 파일이 .data 폴더에 존재하지 않습니다.")

    def extract_date(file):
        match = re.search(r'worldcoffeeportal_(\d{6})\.csv', file)
        return match.group(1) if match else '000000'

    latest_file = max(csv_files, key=extract_date)
    print(f"[불러오기] 최신 기사 파일: {latest_file}")
    return pd.read_csv(latest_file)

# === 2. 커피 가격 데이터 불러오기 ===
def load_price_data():
    price_file = './data/coffee_price.csv'
    if not os.path.exists(price_file):
        raise FileNotFoundError("커피 가격 데이터가 './data/coffee_price.csv'에 없습니다.")
    
    df = pd.read_csv(price_file)
    df['date'] = pd.to_datetime(df['date'])
    return df

# === 3. 기사와 가격 매칭 + 라벨링 ===
def label_articles_by_price_change(articles_df, price_df):
    articles_df['date'] = pd.to_datetime(articles_df['date'])
    merged = pd.merge(articles_df, price_df, on='date', how='left')

    # 다음날 종가 가져오기
    price_df_shifted = price_df.copy()
    price_df_shifted['date'] = price_df_shifted['date'].shift(-1)
    price_df_shifted.rename(columns={'close': 'next_close'}, inplace=True)

    merged = pd.merge(merged, price_df_shifted[['date', 'next_close']], on='date', how='left')
    merged['return'] = (merged['next_close'] - merged['close']) / merged['close'] * 100

    def classify(r):
        if r >= 4:
            return '상승'
        elif r <= -4:
            return '하락'
        else:
            return '중립'

    merged['label'] = merged['return'].apply(classify)
    labeled = merged[['title', 'label']].dropna()
    return labeled

# === 실행 ===
if __name__ == "__main__":
    articles_df = get_latest_article_file()
    price_df = load_price_data()
    labeled_df = label_articles_by_price_change(articles_df, price_df)

    os.makedirs('./processed', exist_ok=True)
    labeled_df.to_csv('./processed/labeled_titles.csv', index=False, encoding='utf-8-sig')
    print(f"[완료] 라벨링된 기사 {len(labeled_df)}개를 './processed/labeled_titles.csv'에 저장했습니다.")
