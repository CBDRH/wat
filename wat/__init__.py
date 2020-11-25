from flask import Flask
from flask import request
from flask import jsonify
from flask_cors import CORS
import json
from io import StringIO
import spacy

nlp = spacy.load('en_core_web_sm')


def create_app():
    app = Flask(__name__)
    # app.config['SECRET_KEY'] = 'test'
    # app.config['CORS_HEADERS'] = 'Content-Type'

    cors = CORS(app, resources={r"/converttobio": {"origins": "http://localhost:3000"}})

    @app.route('/converttobio', methods=['POST'])
    def convert_to_bio():
        if request.method == 'POST':
            data = request.get_data()
            # print(data)
            data = (json.loads(request.data))['data']
            parsedData = parseText(data)
            bioData = text_to_bio(parsedData)
            # print(bioData)
            jsonData = bio_to_json(bioData)
            return jsonify(jsonData)

        # rtn_data = {'token': 'Leibo', 'Tag': 'B-PERSON'}
        return "Error"

    return app


def parseText(text):
    parsed_data = []
    with StringIO(text) as content:
        for line in content:
            parsed_data.append(fetchEntities(line))

    return parsed_data


# parse entities in text
def fetchEntities(text):
    SPAN_ENTITY_START = '<span class="wat-ent-entity"'
    SPAN_ENTITY_MID = '</span><span class="wat-ent-ner"'
    SPAN_ENTITY_END = '</span></span>'
    SPAN_ENTITY_ST = ';">'

    original_text = text
    entities = []
    while original_text.find(SPAN_ENTITY_START) != -1:
        ent_start = original_text.find(SPAN_ENTITY_START)
        ent_mid = original_text.find(SPAN_ENTITY_MID)
        ent_end = original_text.find(SPAN_ENTITY_END)

        ent_words = original_text[ent_start:ent_mid]
        ent_type = original_text[ent_mid:ent_end]

        st_words = ent_words.rfind(SPAN_ENTITY_ST)
        st_type = ent_type.rfind(SPAN_ENTITY_ST)

        ent_words = ent_words[(st_words + len(SPAN_ENTITY_ST)):]
        ent_type = ent_type[st_type + len(SPAN_ENTITY_ST):]

        # print(original_text[ent_start:(ent_end + len(SPAN_ENTITY_END))])

        original_text = original_text.replace(original_text[ent_start:(ent_end + len(SPAN_ENTITY_END))], ent_words, 1)

        # strip words to get exact indices
        start_index = ent_start + (len(ent_words) - len(ent_words.lstrip()))
        end_index = ent_start + len(ent_words) - (len(ent_words) - len(ent_words.rstrip()))
        entity = (start_index, end_index, ent_type)

        # print("[" + ent_words + "]")
        # print(original_text)
        # print(entity)
        entities.append(entity)

    return original_text.replace("\n", ""), {"entities": entities}


# convert list of entities to bio schema with json format
def text_to_bio(data):
    TAG_BEGIN = 'TAGTAGBEGIN'
    TAG_END = 'TAGTAGEND'

    document = []

    for record_txt, record_entities in data:
        entities = record_entities.get('entities', '')

        offset = [0]
        for start, end, entity_tag in entities:
            start_idx = start + sum(offset)
            end_idx = end + sum(offset)
            offset.append(len(TAG_BEGIN) + len(TAG_END) + len(entity_tag) + 4)
            record_txt = record_txt[:start_idx] + ' ' + TAG_BEGIN + entity_tag + ' ' \
                         + record_txt[start_idx:end_idx] + ' ' + TAG_END + ' ' + record_txt[end_idx:]

        record_txt = record_txt.replace('\n', '')

        doc = nlp(record_txt)
        tokens = []
        tokens_bio = []
        entity_begin_flag = False
        entity_middle_flag = False
        entity_type = ''
        entity_token_index = 0
        same_type_entity_together = False
        previous_entity_type = ''

        for token in doc:
            if len(token.text.strip()) == 0:
                continue
            if token.text.startswith(TAG_BEGIN):
                entity_begin_flag = True
                entity_type = token.text[11:]
                if previous_entity_type != '' and previous_entity_type == entity_type:
                    same_type_entity_together = True
                continue

            if token.text.startswith(TAG_END):
                entity_begin_flag = False
                entity_middle_flag = False
                entity_type = ''
                entity_token_index = 0
                continue

            if entity_begin_flag and (not entity_middle_flag):
                entity_token_index += 1
                tokens_bio.append('B-' + entity_type)

                entity_middle_flag = True
                previous_entity_type = entity_type
            elif entity_begin_flag and entity_middle_flag:
                tokens_bio.append('I-' + entity_type)
                entity_token_index += 1
            elif not entity_begin_flag:
                previous_entity_type = ''
                same_type_entity_together = False
                tokens_bio.append('O')
            tokens.append(token.text)

        if len(tokens) != len(tokens_bio):
            raise Exception('Token length should be the same as BIO tag length')

        document.append(list(zip(tokens, tokens_bio)))

    return document


def bio_to_json(bio_data):
    ent_dict = {"result": []}

    for line in bio_data:
        for token, tag in line:
            ent_dict["result"].append({
                "token": token,
                "tag": tag
            })
        ent_dict["result"].append({
            "token": '\n',
            "tag": ''
        })
    return ent_dict
