from sqlalchemy import bindparam, create_engine, text
import pandas as pd
from config import DB_CONNECTION_STRING, TARGET_QB_ID, RTU_CUSTOMER_ID


def get_engine():
    return create_engine(DB_CONNECTION_STRING)


def fetch_qb_list(search="", limit=50):
    engine = get_engine()
    query = text("""
        SELECT TOP (:limit)
            QBId,
            QBName,
            Tags,
            CreatedOn,
            NoOfQues,
            Status,
            CustomerId
        FROM dbo.QuestionBankMaster
        WHERE Status = 1
          AND CustomerId = :rtu_customer_id
          AND (
                QBName LIKE :search
                OR CAST(QBId AS VARCHAR) LIKE :search
              )
        ORDER BY QBName ASC
    """)
    search_param = f"%{search}%"
    df = pd.read_sql(query, engine, params={"limit": limit, "search": search_param, "rtu_customer_id": RTU_CUSTOMER_ID})
    return df.to_dict("records")


def fetch_logicbox_qb_list(search="", limit=50):
    engine = get_engine()
    search_param = f"%{search}%"
    logicbox_patterns = ["%logicbox%", "%LogicBox%", "%logic box%", "%Logic Box%", "%LB_%", "%_LB"]
    like_conditions = [f"QBName LIKE :p{i}" for i in range(len(logicbox_patterns))]
    like_clause = " OR ".join(like_conditions)

    query = text(f"""
        SELECT TOP (:limit)
            QBId,
            QBName,
            Tags,
            CreatedOn,
            NoOfQues,
            Status,
            CustomerId
        FROM dbo.QuestionBankMaster
        WHERE Status = 1
          AND CustomerId = :rtu_customer_id
          AND (
                QBName LIKE :search
                OR CAST(QBId AS VARCHAR) LIKE :search
              )
          AND ({like_clause})
        ORDER BY QBName ASC
    """)

    params = {"limit": limit, "search": search_param, "rtu_customer_id": RTU_CUSTOMER_ID}
    for i, pattern in enumerate(logicbox_patterns):
        params[f"p{i}"] = pattern

    df = pd.read_sql(query, engine, params=params)
    return df.to_dict("records")


def fetch_questions_for_qb(qb_id):
    engine = get_engine()

    query = text("""
        SELECT qm.QueId, qm.QBId, qm.QueTypeId, qm.Question, qm.DifficultyLevel, qm.Tags, qm.Status,
               qbm.QBName
        FROM QuestionMasters qm
        JOIN dbo.QuestionBankMaster qbm ON qbm.QBId = qm.QBId
        WHERE qm.QBId = :qb_id
          AND qm.Status = 1
          AND qbm.Status = 1
          AND qbm.CustomerId = :rtu_customer_id
        ORDER BY qm.CreatedOn DESC
    """)

    df = pd.read_sql(query, engine, params={"qb_id": qb_id, "rtu_customer_id": RTU_CUSTOMER_ID})
    return df


def fetch_logicbox_questions(limit=500):
    engine = get_engine()
    logicbox_patterns = ["%logicbox%", "%LogicBox%", "%logic box%", "%Logic Box%", "%LB_%", "%_LB"]
    like_conditions = [f"QBName LIKE :p{i}" for i in range(len(logicbox_patterns))]
    like_clause = " OR ".join(like_conditions)
    params = {"limit": limit, "rtu_customer_id": RTU_CUSTOMER_ID}
    for i, pattern in enumerate(logicbox_patterns):
        params[f"p{i}"] = pattern

    qb_query = text(f"""
        SELECT QBId, QBName
        FROM dbo.QuestionBankMaster
        WHERE Status = 1
          AND CustomerId = :rtu_customer_id
          AND ({like_clause})
        ORDER BY QBName ASC
    """)
    qb_df = pd.read_sql(qb_query, engine, params=params)
    if qb_df.empty:
        return pd.DataFrame()

    qb_ids = qb_df["QBId"].tolist()
    qb_names = qb_df.set_index("QBId")["QBName"].to_dict()

    questions_query = text("""
        SELECT QueId, QBId, LEFT(Question, 150) AS Preview, DifficultyLevel, Status
        FROM QuestionMasters
        WHERE QBId IN :qb_ids AND Status = 1
        ORDER BY QBId, CreatedOn DESC
    """).bindparams(bindparam("qb_ids", expanding=True))

    questions_df = pd.read_sql(questions_query, engine, params={"qb_ids": qb_ids})

    if not questions_df.empty and "QBName" not in questions_df.columns:
        questions_df["QBName"] = questions_df["QBId"].map(qb_names)

    return questions_df


def fetch_question_by_que_id(que_id):
    engine = get_engine()
    lookup = text("""
        SELECT QueId, QBId, QueTypeId, Question, DifficultyLevel,
               Tags, Points, AnswerKeys_Comments, AnswerExplanation,
               Status, CreatedOn, ModifiedOn
        FROM QuestionMasters
        WHERE QueId = :que_id
          AND Status = 1
    """)
    df = pd.read_sql(lookup, engine, params={"que_id": int(que_id)})
    if df.empty:
        return None

    row = df.iloc[0].to_dict()
    qb_id = int(row.get("QBId", 0) or 0)
    if qb_id <= 0:
        return None

    qb_owner_query = text("""
        SELECT QBId
        FROM dbo.QuestionBankMaster
        WHERE QBId = :qb_id
          AND Status = 1
          AND CustomerId = :rtu_customer_id
    """)
    owner_df = pd.read_sql(qb_owner_query, engine, params={"qb_id": qb_id, "rtu_customer_id": RTU_CUSTOMER_ID})
    if owner_df.empty:
        return None

    answers_query = text("""
        SELECT AnsId, QueId, Answer, IsCorrect, Points, AnswerIntent, Status
        FROM QuestionMaster_Answer
        WHERE QueId = :que_id
        ORDER BY AnsId
    """)
    answers_df = pd.read_sql(answers_query, engine, params={"que_id": int(que_id)})
    row["Answers"] = answers_df.to_dict("records")

    return row


def fetch_answers_for_questions(que_ids):
    if not que_ids:
        return pd.DataFrame()

    engine = get_engine()
    query = text("""
        SELECT AnsId, QueId, Answer, IsCorrect, Points, AnswerIntent, Status
        FROM QuestionMaster_Answer
        WHERE QueId IN :que_ids
        ORDER BY QueId, AnsId
    """).bindparams(bindparam("que_ids", expanding=True))

    df = pd.read_sql(query, engine, params={"que_ids": [int(q) for q in que_ids]})
    return df


def fetch_question_types(qb_id):
    engine = get_engine()
    query = text("""
        SELECT DISTINCT QueTypeId
        FROM QuestionMasters
        WHERE QBId = :qb_id AND Status = 1
        ORDER BY QueTypeId
    """)
    df = pd.read_sql(query, engine, params={"qb_id": int(qb_id)})
    return [int(row["QueTypeId"]) for _, row in df.iterrows()]


def fetch_full_questions(qb_id=TARGET_QB_ID, limit=None, que_ids=None):
    if que_ids:
        engine = get_engine()
        normalized_que_ids = [int(qid) for qid in que_ids]
        query = text("""
            SELECT QueId, QBId, QueTypeId, Question, DifficultyLevel,
                   Tags, Points, AnswerKeys_Comments, AnswerExplanation,
                   Status, CreatedOn, ModifiedOn
            FROM QuestionMasters
            WHERE QueId IN :que_ids
              AND QBId IN (
                  SELECT QBId
                  FROM dbo.QuestionBankMaster
                  WHERE QBId IN (
                      SELECT DISTINCT QBId
                      FROM QuestionMasters
                      WHERE QueId IN :que_ids
                  )
                    AND Status = 1
                    AND CustomerId = :rtu_customer_id
              )
            ORDER BY QueId
        """).bindparams(bindparam("que_ids", expanding=True))
        questions_df = pd.read_sql(query, engine, params={"que_ids": normalized_que_ids, "rtu_customer_id": RTU_CUSTOMER_ID})
    else:
        questions_df = fetch_questions(qb_id=qb_id, limit=limit)

    if questions_df.empty:
        return []

    que_ids = questions_df["QueId"].tolist()
    answers_df = fetch_answers_for_questions(que_ids)

    questions = []
    for _, row in questions_df.iterrows():
        que_id = row["QueId"]
        related_answers = answers_df[answers_df["QueId"] == que_id]

        questions.append({
            "QueId": int(que_id),
            "QBId": int(row["QBId"]),
            "QueTypeId": row["QueTypeId"],
            "Question": row["Question"],
            "DifficultyLevel": row["DifficultyLevel"],
            "Tags": row["Tags"],
            "Points": row["Points"],
            "AnswerKeys_Comments": row["AnswerKeys_Comments"],
            "AnswerExplanation": row["AnswerExplanation"],
            "Answers": related_answers.to_dict("records"),
            "Status": row["Status"],
        })

    return questions


def fetch_questions(qb_id=TARGET_QB_ID, status=1, limit=None, batch_size=None):
    engine = get_engine()

    query = """
        SELECT QueId, QBId, QueTypeId, Question, DifficultyLevel,
               Tags, Points, AnswerKeys_Comments, AnswerExplanation,
               Status, CreatedOn, ModifiedOn
        FROM QuestionMasters
        WHERE QBId = :qb_id
          AND Status = :status
          AND QBId IN (
              SELECT QBId
              FROM dbo.QuestionBankMaster
              WHERE QBId = :qb_id
                AND Status = 1
                AND CustomerId = :rtu_customer_id
          )
        ORDER BY CreatedOn DESC
    """
    if batch_size is not None and limit is None:
        limit = batch_size

    params = {"qb_id": qb_id, "status": status, "rtu_customer_id": RTU_CUSTOMER_ID}

    if limit is not None:
        query += " OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY"
        params["limit"] = int(limit)

    df = pd.read_sql(text(query), engine, params=params)
    return df