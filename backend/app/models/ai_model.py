import joblib
import pandas as pd

#프론트 & 백엔드 개발용 Dummy 모델
model_data = joblib.load("app/ml/model.pkl")

model = model_data["model"]
scaler = model_data["scaler"]

#Dummy 모델 속성
FEATURE_NAMES = ["area", "floor", "building_ages", "subway_distance"]

#모델을 사용한 예측 (Dummy Model)
def predict_price(features):
    features_df = pd.DataFrame([features], columns=FEATURE_NAMES)
    features_scaled = scaler.transform(features_df)
    prediction = model.predict(features_scaled)
    
    return float(prediction[0])