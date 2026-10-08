<p align="center">
  <img width="320" height="160" alt="제목을 입력해주세요" src="https://github.com/user-attachments/assets/16b11e24-2fb2-4af4-9e82-ca2df49853d2" />
</p>
<p align="center">
  <strong>재건축 재개발 분담금 예측을 간편하게 사용해보세요.</strong>
</p>

<p align="center">
  얼마 GEO 는 지도를 통하여 간편하게 구간에 대하여
  AI 를 사용한 분담금 예측을 진행해주는 웹 서비스입니다.
</p>

<img width="1024" height="570" alt="제목을 입력해주세요  (4)" src="https://github.com/user-attachments/assets/438b2688-6835-4e64-8358-20f1aca91e63" />

# 1. 서비스 개요

서비스 링크

https://04-howmuch-geo-ntnl.vercel.app/

<img width="1920" height="1080" alt="2" src="https://github.com/user-attachments/assets/f2e79e28-a80b-43eb-9b32-c3942389596b" />

<img width="1920" height="1080" alt="3" src="https://github.com/user-attachments/assets/ca3d2eb0-dc67-48cc-b2ac-94ed8b1f4c2a" />

<img width="1920" height="1080" alt="4" src="https://github.com/user-attachments/assets/3892d6ff-5b4f-42f5-8bd2-446f555359b1" />

<img width="1920" height="1080" alt="5" src="https://github.com/user-attachments/assets/39a47f1c-8c52-4351-b424-a27197bdb246" />

<img width="1920" height="1080" alt="6" src="https://github.com/user-attachments/assets/f4c16b22-4408-4aaf-aca3-a4c27f3b09e6" />


# 2. 기술 스택

| 구분                 | 기술 스택                                               |
|:---------------------|:--------------------------------------------------------|
| Frontend             | Tailwind, Typescript, Axios, Vite             |
| Backend              | Python, FastAPI, httpx, PostgreSQL, Redis               |
| API                  | Kakao SDK API, Kakao Pay API, V-World API, 공공데이터포털 API           |
| CI/CD                | Vercel, Render, Github Action                           |

# 3. 주요 기능
- 백엔드 엔드포인트

| 엔드포인트 라우터 카테고리        | API 엔드포인트                                                     | 설명                                                     |
|:---------------------------|:----------------------------------------------------------------|:---------------------------------------------------------|
| Cadastral Router           | GET /api/v1/cadastral                                           | 필지 조회 API                                              |
| Zone Router                | POST /api/v1/zone                                               | 슬라이더 및 기본 정보 조합 API                                 |
| Contribution Router        | POST /api/v1/contribution                                       | 최종 분담금 계산 API                                         |
| User Router                | POST /api/v1/user/signup                                        | 사용자 회원가입 API                                          |
| User Router                | POST /api/v1/user/login                                         | 사용자 로그인 API                                           |
| User Router                | GET /api/v1/user/logout                                         | 사용자 로그아웃 API                                          |
| User Router                | GET /api/v1/user/info                                           | 사용자 정보 조회 API                                         |
| User Router                | GET /api/v1/user/credits                                        | 사용자 개인 크레딧 개수 조회 API                                |
| User Router                | GET /api/v1/user/credits/reset                                  | 사용자 개인 크레딧 초기화 API                                  |
| News Router                | POST /api/v1/news                                               | 지역 이름을 바탕으로 정보 검색 조회 API                          |
| Payment Router             | POST /api/v1/kakao-pay/credits/ready                            | 개인 계정 크레딧 충전 준비 API                                 |
| Payment Router             | GET /api/v1/kakao-pay/credits/approve                           | 개인 계정 크레딧 충전 승인 API                                 |
| Payment Router             | GET /api/v1/kakao-pay/credits/cancel                            | 개인 계정 크레딧 충전 취소 API                                 |
| Payment Router             | GET /api/v1/kakao-pay/credits/fail                              | 개인 계정 크레딧 충전 실패 API                                 |
| Payment Router             | POST /api/v1/kakao-pay/plans/ready                              | 조합 plan 결제 준비 API                                     |
| Payment Router             | GET /api/v1/kakao-pay/plans/approve                             | 조합 plan 결제 승인 API                                     |
| Payment Router             | GET /api/v1/kakao-pay/plans/cancel                              | 조합 plan 결제 취소 API                                     |
| Payment Router             | GET /api/v1/kakao-pay/plans/fail                                | 조합 plan 결제 실패 API                                     |
| Organization Router        | GET /api/v1/organization/scenarios                              | 조합 내 저장된 필지 묶음 전체 조회 API                           |
| Organization Router        | POST /api/v1/organization/scenarios                             | 조합 내 필지 묶음 저장 API                                    |
| Organization Router        | GET /api/v1/organization/scenarios/{scenario_id}                | 조합 내 필지 묶음 중 단일 묶음 불러오기 API                       |
| Organization Router        | DELETE /api/v1/organization/scenarios/{scenario_id}             | 조합 내 필지 묶음 중 단일 묶음 삭제 API                          |
| Organization Router        | GET /api/v1/organization/me                                     | 가입된 조합 조회 API                                         |
| Organization Router        | POST /api/v1/organization/join                                  | 조합 신청 API                                              |
| Organization Router        | DELETE /api/v1/organization/leave                               | 가입된 조합 탈퇴 API                                         |
| Organization Router        | GET /api/v1/organization/members                                | 조합내 인원 전체 조회 API                                     |
| Organization Router        | POST /api/v1/organization/members/{member_user_id}/approve      | 조합 신청 사용자 승인 API                                     |
| Organization Router        | DELETE /api/v1/organization/members/{member_user_id}            | 조합장의 조합 인원 삭제 API                                    |





# 4. 아키텍쳐

- 시스템 아키텍쳐
<img width="1671" height="1632" alt="System Arcitecture drawio (1)" src="https://github.com/user-attachments/assets/ab5436aa-5638-4792-bd64-0eb82436820f" />

- ERD
<img width="932" height="824" alt="ERD drawio (6)" src="https://github.com/user-attachments/assets/8e2aa7fd-278b-4016-873b-bba80f95888a" />


- Directory 아키텍쳐
```
├── AI
│   ├── engine
│   │   ├── calc.py
│   │   ├── data
│   │   │   └── policy_rules.json
│   │   ├── policy.py
│   │   ├── prior_asset.py
│   │   ├── project_type.py
│   │   ├── public_contribution.py
│   │   ├── rental_cost.py
│   │   ├── schema.py
│   │   └── zone.py
│   ├── maintenance
│   │   └── policy_watch.py
│   └── predict
│       ├── construction_cost.py
│       ├── data
│       │   ├── bjdong_codes.md
│       │   ├── cost_cases.csv
│       │   ├── cost_index.csv
│       │   ├── sale_cases.csv
│       │   └── sale_index.csv
│       ├── predictions.py
│       ├── sale_price.py
│       └── trend.py
├── PIPELINE.md
├── README.md
├── backend
│   ├── AI
│   ├── Dockerfile
│   ├── README.md
│   ├── app
│   │   ├── auth
│   │   │   └── encrypt.py
│   │   ├── cache
│   │   │   └── redis.py
│   │   ├── config
│   │   │   └── engine_defaults.py
│   │   ├── database
│   │   │   ├── database_connection.py
│   │   │   └── orm.py
│   │   ├── exceptions
│   │   │   └── exceptions_handler.py
│   │   ├── main.py
│   │   ├── models
│   │   │   ├── account.py
│   │   │   ├── credit_purchase.py
│   │   │   ├── organization_scenario.py
│   │   │   └── user.py
│   │   ├── routers
│   │   │   ├── cadastral.py
│   │   │   ├── contribution.py
│   │   │   ├── news.py
│   │   │   ├── organization.py
│   │   │   ├── payment.py
│   │   │   ├── user.py
│   │   │   └── zone.py
│   │   ├── schemas
│   │   │   ├── cadastral
│   │   │   │   ├── cadastral_request.py
│   │   │   │   └── cadastral_response.py
│   │   │   ├── news
│   │   │   │   ├── news_request.py
│   │   │   │   └── news_response.py
│   │   │   ├── organization_scenario.py
│   │   │   ├── payment
│   │   │   │   ├── payment_request.py
│   │   │   │   └── payment_response.py
│   │   │   ├── realestate
│   │   │   │   ├── realestate_request.py
│   │   │   │   └── realestate_response.py
│   │   │   └── user
│   │   │       ├── user_request.py
│   │   │       └── user_response.py
│   │   ├── services
│   │   │   ├── building_ledger_service.py
│   │   │   ├── credit_service.py
│   │   │   ├── organization_service.py
│   │   │   ├── plan_service.py
│   │   │   └── zone_service.py
│   │   └── utils
│   │       └── slider_builder.py
│   └── requirements.txt
├── docker-compose.yml
├── frontend
│   ├── Dockerfile
│   ├── README.md
│   ├── WARNING_COPY.md
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   ├── public
│   │   ├── banner.png
│   │   ├── favicon.png
│   │   ├── icon.png
│   │   └── icons.svg
│   ├── src
│   │   ├── App.tsx
│   │   ├── api
│   │   │   ├── cadastral_api.ts
│   │   │   ├── client.ts
│   │   │   ├── news_api.ts
│   │   │   ├── organization_api.ts
│   │   │   ├── payment_api.ts
│   │   │   ├── realestate_api.ts
│   │   │   └── user_api.ts
│   │   ├── components
│   │   │   ├── ContributionPanel.tsx
│   │   │   ├── KakaoMap.tsx
│   │   │   ├── MapLegend.tsx
│   │   │   ├── ModelPredictForm.tsx
│   │   │   ├── NewsPanel.tsx
│   │   │   ├── SideBar.tsx
│   │   │   ├── Slider.tsx
│   │   │   └── StartupModal.tsx
│   │   ├── hooks
│   │   │   ├── useContribution.ts
│   │   │   ├── useKakaoMap.ts
│   │   │   ├── useLoginPage.ts
│   │   │   ├── useMainPage.ts
│   │   │   ├── useMapDragSelect.ts
│   │   │   ├── useModelPredictForm.ts
│   │   │   ├── useNewsPanel.ts
│   │   │   ├── useOrganizationPage.ts
│   │   │   ├── useSignupPage.ts
│   │   │   └── useSlider.ts
│   │   ├── index.css
│   │   ├── main.tsx
│   │   ├── pages
│   │   │   ├── CreditPurchasePage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── MainPage.tsx
│   │   │   ├── OrganizationPage.tsx
│   │   │   ├── PaymentPage.tsx
│   │   │   └── SignupPage.tsx
│   │   └── utils
│   │       └── parcel.ts
│   ├── tsconfig.json
│   └── vite.config.ts
└── vercel.json


```


