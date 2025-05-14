# # 1. 설치
# !pip install transformers nltk torch pandas --quiet

# 2. 임포트
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

# 3. NLTK 불용어 다운로드
nltk.download("stopwords")
stop_words = set(stopwords.words("english"))

# 4. 뉴스 + 가격 CSV 불러오기
daily = pd.read_csv("/content/dailycoffeenews_250503.csv")
portal = pd.read_csv("/content/worldcoffeeportal_250503.csv")
price_df = pd.read_csv("/content/coffee_c_price.csv")

# 5. 뉴스 병합
daily["date"] = pd.to_datetime(daily["date"])
portal["date"] = pd.to_datetime(portal["date"])
news_df = pd.concat([daily, portal], ignore_index=True)
grouped = news_df.groupby("date")["title"].apply(lambda x: " ".join(x.astype(str))).reset_index()
grouped = grouped.rename(columns={"title": "combined_titles"})

# 6. 전처리 함수
def preprocess(text):
    text = str(text).lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    tokens = text.split()
    tokens = list(set([word for word in tokens if word not in stop_words]))
    return " ".join(tokens)

grouped["processed_text"] = grouped["combined_titles"].apply(preprocess)

# 7. 감성 분석 모델 로드
# 모델 1: twitter-roberta (3-class)
model1 = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer1 = AutoTokenizer.from_pretrained(model1)
model1 = AutoModelForSequenceClassification.from_pretrained(model1)
pipe1 = pipeline("sentiment-analysis", model=model1, tokenizer=tokenizer1)

# 모델 2: distilbert (2-class)
model2 = "distilbert-base-uncased-finetuned-sst-2-english"
tokenizer2 = AutoTokenizer.from_pretrained(model2)
model2 = AutoModelForSequenceClassification.from_pretrained(model2)
pipe2 = pipeline("sentiment-analysis", model=model2, tokenizer=tokenizer2)

# 모델 3: FinBERT (3-class for finance)
model3 = "ProsusAI/finbert"
tokenizer3 = AutoTokenizer.from_pretrained(model3)
model3 = AutoModelForSequenceClassification.from_pretrained(model3)
pipe3 = pipeline("sentiment-analysis", model=model3, tokenizer=tokenizer3)

# 8. 감성 분석 실행
texts = grouped["processed_text"].tolist()

results1 = pipe1(texts)
results2 = pipe2(texts)
results3 = pipe3(texts)

# 결과 저장
grouped["sentiment_label_1"] = [res["label"] for res in results1]
grouped["sentiment_score_1"] = [res["score"] for res in results1]
grouped["sentiment_label_2"] = [res["label"] for res in results2]
grouped["sentiment_score_2"] = [res["score"] for res in results2]
grouped["sentiment_label_finbert"] = [res["label"] for res in results3]
grouped["sentiment_score_finbert"] = [res["score"] for res in results3]

# 9. 가격 데이터 병합
price_df["Date"] = pd.to_datetime(price_df["Date"])
price_df["price_change_pct"] = price_df["Coffee_Price"].pct_change() * 100
grouped["date"] = pd.to_datetime(grouped["date"])
merged = pd.merge(grouped, price_df, left_on="date", right_on="Date", how="inner")

# 10. 가격 변동 라벨링
def label_price_movement(pct):
    if pd.isna(pct):
        return None
    elif pct >= 4.0:
        return "up"
    elif pct <= -4.0:
        return "down"
    else:
        return "neutral"

merged["price_movement"] = merged["price_change_pct"].apply(label_price_movement)

# 11. 저장
merged.to_csv("/content/final_sentiment_price_with_finbert.csv", index=False)
print("저장 완료: /content/final_sentiment_price_with_finbert.csv")
