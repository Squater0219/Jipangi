# Database ERD

프로젝트 데이터베이스 구조는 이메일 로그인을 사용하는 사용자 테이블(`user_account`)과 발음 분석 도메인 테이블 5개로 구성된다.

```mermaid
%%{init: {"flowchart": {"defaultRenderer": "elk", "nodeSpacing": 80, "rankSpacing": 120}}}%%
erDiagram
    direction LR

    USER_ACCOUNT ||--o{ PRONUNCIATION_ANALYSIS : creates
    PRACTICE_SENTENCE ||--o{ PRONUNCIATION_ANALYSIS : analyzed_by
    PRONUNCIATION_CATEGORY ||--o{ PRACTICE_SENTENCE : groups
    PRONUNCIATION_ANALYSIS ||--o{ PRONUNCIATION_ERROR : has
    PRONUNCIATION_ANALYSIS ||--o| CORRECTION_FEEDBACK : receives

    USER_ACCOUNT {
        bigint id PK
        string email UK
        string username
        boolean is_active
        boolean is_staff
        datetime date_joined
    }

    PRONUNCIATION_CATEGORY {
        bigint id PK
        string code UK
        string name UK
        text description
        datetime created_at
        datetime updated_at
    }

    PRACTICE_SENTENCE {
        bigint id PK
        string text UK
        json cached_ipa
        json word_spans
        smallint difficulty
        bigint category_id FK
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    PRONUNCIATION_ANALYSIS {
        uuid id PK
        bigint user_id FK
        bigint sentence_id FK
        json target_ipa
        json recognized_ipa
        json alignment
        decimal score
        string status
        boolean consent_to_store
        datetime expires_at
        int processing_ms
        json analyzer_metadata
        text failure_reason
        datetime created_at
        datetime updated_at
    }

    PRONUNCIATION_ERROR {
        bigint id PK
        uuid analysis_id FK
        int sequence
        int phone_position
        string word
        int word_index
        string target_phone
        string recognized_phone
        string operation
        decimal confidence
        datetime created_at
    }

    CORRECTION_FEEDBACK {
        bigint id PK
        uuid analysis_id FK,UK
        string summary
        text content
        json priority_items
        json structured_output
        string model_name
        string model_version
        boolean is_validated
        datetime created_at
        datetime updated_at
    }
```

## Relationship Summary

- `user_account` 1:N `pronunciation_analysis`
- `pronunciation_category` 1:N `practice_sentence`
- `practice_sentence` 1:N `pronunciation_analysis`
- `pronunciation_analysis` 1:N `pronunciation_error`
- `pronunciation_analysis` 1:0..1 `correction_feedback`

## How To View

1. VS Code에서 이 파일을 연다.
2. 확장 프로그램 `Markdown Preview Mermaid Support`를 설치한다.
3. `Command + Shift + V`로 Markdown Preview를 연다.

GitHub에 올리면 Mermaid 코드 블록이 자동으로 ERD로 렌더링된다.

대안으로 https://mermaid.live 에 위 Mermaid 코드 블록을 붙여넣어 바로 볼 수 있다.
