# 데이터 파일 분리 및 .gitignore 관리 구현 계획안

본 계획안은 GitHub 배포를 위해 5GB가 넘는 대용량 따릉이 일별 원본 CSV 파일들을 업로드 대상에서 배제하고, 예측 서비스에 필수적인 경량 전처리 완료 파일(24KB) 및 기상 정보만을 구분하여 형상관리(.gitignore)에 반영하기 위한 설계입니다.

---

## 사용자 검토 요구사항 (User Review Required)

> [!IMPORTANT]
> **폴더 구조 변경에 따른 코드 경로 수정**
> 데이터를 대용량 원본 폴더(`source_data/large_raw/`)와 업로드용 가공 폴더(`source_data/processed/`)로 물리적으로 분리함에 따라, 기존의 [app.py](file:///d:/MyMLProject/app.py) 및 [bite_demand_prediction_1.ipynb](file:///d:/MyMLProject/bite_demand_prediction_1.ipynb), [bite_demand_prediction_1.py](file:///d:/MyMLProject/bite_demand_prediction_1.py) 파일 내의 파일 경로 설정을 그에 맞춰 수정해야 합니다.

---

## 오픈 질문 (Open Questions)

> [!NOTE]
> **폴더 명칭 및 구조 확정**
> 아래와 같은 폴더 구조로 정리할 계획입니다. 혹시 변경을 원하시는 명칭이 있으시면 피드백해 주십시오.
> *   `source_data/large_raw/` : GitHub 업로드 대상에서 **제외(Ignore)**할 36개의 대용량 원본 파일
> *   `source_data/processed/` : GitHub에 **업로드**할 통합 대여량 데이터 및 기상 정보 폴더

---

## 제안된 변경 사항 (Proposed Changes)

### 1. 폴더 구조 변경 및 파일 이동

*   **[NEW]** `source_data/large_raw/` 폴더를 생성하고, `서울특별시 공공자전거 이용정보(일별)_2301.csv` 등 36개 원본 파일을 이 폴더로 이동합니다.
*   **[NEW]** `source_data/processed/` 폴더를 생성하고, 기존의 `서울_2023-2025_공공자전거_이용정보_통합.csv` 및 `서울기상정보/` 디렉토리 전체를 이 폴더 하위로 이동합니다.

---

### 2. 코드 및 설정 파일 수정

#### [NEW] [.gitignore](file:///d:/MyMLProject/.gitignore)
*   프로젝트 루트에 새로운 깃 무시 설정 파일을 생성합니다.
*   가상환경(`.venv/`), 파이썬 컴파일 캐시(`__pycache__/`), 그리고 대용량 원본 데이터 폴더(`source_data/large_raw/`)를 배제 대상으로 등록합니다.

#### [MODIFY] [app.py](file:///d:/MyMLProject/app.py)
*   **기상 및 통합 대여량 경로 수정:**
    *   기존:
        ```python
        RENTAL_FILE_INTG = "./source_data/서울_2023-2025_공공자전거_이용정보_통합.csv"
        WEATHER_FILE = "./source_data/서울기상정보/2023-2025_서울_일별_기상정보_통합.csv"
        ```
    *   변경:
        ```python
        RENTAL_FILE_INTG = "./source_data/processed/서울_2023-2025_공공자전거_이용정보_통합.csv"
        WEATHER_FILE = "./source_data/processed/서울기상정보/2023-2025_서울_일별_기상정보_통합.csv"
        ```

#### [MODIFY] [bite_demand_prediction_1.py](file:///d:/MyMLProject/bite_demand_prediction_1.py) 및 [bite_demand_prediction_1.ipynb](file:///d:/MyMLProject/bite_demand_prediction_1.ipynb)
*   **환경설정 상수 값 변경:**
    *   기존:
        ```python
        RENTAL_DIR = "source_data"
        RENTAL_FILE_INTG = "./source_data/서울_2023-2025_공공자전거_이용정보_통합.csv"
        WEATHER_FILE = "./source_data/서울기상정보/2023-2025_서울_일별_기상정보_통합.csv"
        ```
    *   변경:
        ```python
        RENTAL_DIR = "source_data/large_raw"
        RENTAL_FILE_INTG = "./source_data/processed/서울_2023-2025_공공자전거_이용정보_통합.csv"
        WEATHER_FILE = "./source_data/processed/서울기상정보/2023-2025_서울_일별_기상정보_통합.csv"
        ```

---

## 검증 계획 (Verification Plan)

### 자동 검증
*   구조 개편 후 Python 컴파일 체크 및 Streamlit 실행성 테스트:
    ```bash
    .venv\Scripts\python.exe -m py_compile app.py
    .venv\Scripts\python.exe -m py_compile bite_demand_prediction_1.py
    ```

### 수동 검증 및 Git 배제 검사
1.  Git 상태 조회를 통해 대용량 원본 파일들이 업로드 대상으로 잡히지 않는지 확인:
    ```bash
    git status
    ```
2.  Streamlit 서버를 구동하여 파일 경로 수정 후에도 실시간 대시보드가 정상 작동하는지 브라우저에서 최종 확인합니다.
