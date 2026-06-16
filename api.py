import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import bindparam, create_engine, text
from config import DB_CONNECTION_STRING
import pandas as pd

app = Flask(__name__)
CORS(app)


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
          AND (
                QBName LIKE :search
                OR CAST(QBId AS VARCHAR) LIKE :search
              )
        ORDER BY QBName ASC
    """)
    search_param = f"%{search}%"
    df = pd.read_sql(query, engine, params={"limit": limit, "search": search_param})
    return df.to_dict("records")


def fetch_logicbox_qb_list(search="", limit=50, logicbox_identifiers=None):
    engine = get_engine()
    if logicbox_identifiers is None:
        logicbox_identifiers = []

    conditions = ["Status = 1"]
    params = {"limit": limit, "search": f"%{search}%"}

    if logicbox_identifiers:
        id_conditions = []
        for idx, ident in enumerate(logicbox_identifiers):
            param_name = f"ident_{idx}"
            id_conditions.append(f"QBName LIKE :{param_name}")
            params[param_name] = f"%{ident}%"
        if id_conditions:
            conditions.append("(" + " OR ".join(id_conditions) + ")")

    where_clause = " AND ".join(conditions)

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
        WHERE {where_clause}
          AND (
                QBName LIKE :search
                OR CAST(QBId AS VARCHAR) LIKE :search
              )
        ORDER BY QBName ASC
    """)

    df = pd.read_sql(query, engine, params=params)
    return df.to_dict("records")


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


@app.route("/api/question-banks", methods=["GET"])
def api_question_banks():
    search = request.args.get("search", "")
    limit = int(request.args.get("limit", 20000))
    rows = fetch_qb_list(search=search, limit=limit)
    return jsonify(rows)


@app.route("/api/logicbox-qbs", methods=["GET"])
def api_logicbox_qbs():
    search = request.args.get("search", "")
    limit = int(request.args.get("limit", 50))
    identifiers = request.args.get("identifiers", "").split(",") if request.args.get("identifiers") else []
    identifiers = [i.strip() for i in identifiers if i.strip()]
    rows = fetch_logicbox_qb_list(search=search, limit=limit, logicbox_identifiers=identifiers)
    return jsonify(rows)


@app.route("/api/question-types", methods=["GET"])
def api_question_types():
    qb_id = request.args.get("qb_id")
    if not qb_id:
        return jsonify({"error": "qb_id is required"}), 400
    types = fetch_question_types(int(qb_id))
    return jsonify(types)


@app.route("/api/questions/<int:qb_id>", methods=["GET"])
def api_questions(qb_id):
    engine = get_engine()
    query = text("""
        SELECT QueId, LEFT(Question, 150) AS Preview, DifficultyLevel, Status
        FROM QuestionMasters
        WHERE QBId = :qb_id AND Status = 1
        ORDER BY CreatedOn DESC
    """)
    df = pd.read_sql(query, engine, params={"qb_id": qb_id})
    return jsonify(df.to_dict("records"))


@app.route("/api/question/<int:que_id>", methods=["GET"])
def api_question_by_id(que_id):
    engine = get_engine()

    query = text("""
        SELECT QueId, QBId, QueTypeId, Question, DifficultyLevel,
               Tags, Points, AnswerKeys_Comments, AnswerExplanation,
               Status, CreatedOn, ModifiedOn
        FROM QuestionMasters
        WHERE QueId = :que_id
    """)
    df = pd.read_sql(query, engine, params={"que_id": int(que_id)})
    if df.empty:
        return jsonify({"error": "Question not found"}), 404

    row = df.iloc[0].to_dict()

    answers_query = text("""
        SELECT AnsId, QueId, Answer, IsCorrect, Points, AnswerIntent, Status
        FROM QuestionMaster_Answer
        WHERE QueId = :que_id
        ORDER BY QueId, AnsId
    """)
    answers_df = pd.read_sql(answers_query, engine, params={"que_id": int(que_id)})
    row["Answers"] = answers_df.to_dict("records")

    return jsonify(row)


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
