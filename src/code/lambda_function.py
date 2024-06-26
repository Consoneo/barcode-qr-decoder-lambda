import json, tempfile, time, os, mysql.connector, boto3, botocore, logging, pytz
from pyzbar.pyzbar import decode
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from datetime import datetime
from urllib.parse import unquote_plus
from PIL import Image

S3 = boto3.client('s3', 'eu-west-1', config=botocore.config.Config(s3={'addressing_style':'path'}))
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_DATABASE = os.environ.get('DB_DATABASE')
DB_CONFIG = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': DB_HOST,
    'database': DB_DATABASE
}
DB_TABLE = 'DocumentQrDecode'
logging.basicConfig(level = logging.INFO)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Check the number of letters for the doc type. In dossier-c2e, this one is necessary to find the good docType
def check_doc_type_letter(letters: str) -> bool:
    if len(letters) >= 1:
        return True
    return False

# Check the number of character for the entity reference. In dossier-c2e, this one is necessary to find the good entity
def check_reference(reference: str) -> bool:
    if len(reference) >= 14 and not 'http' in reference:
        return True
    return False

# Check the number of letter for the type entity. In dossier-c2e, this one is necessary to find the good entity
# I = InstallateurUser
# O = OffreProjet
def check_entity_letter(letter: str) -> bool:
    if len(letter) == 1:
        return True
    return False

def is_valid_document_data(data: list) -> bool:
    return len(data) == 3 and check_doc_type_letter(data[0]) and check_reference(data[1]) and check_entity_letter(data[2])

def is_valid_document_reference(data: list) -> bool:
    return len(data) == 1 and check_reference(data[0])

def get_sql_update(document_qr_decode: dict) -> str: 
    update_values = ""
    for column,value in document_qr_decode.items():
        if value != None:
            update_values = update_values + f"`{column}` = '{value}', "
    query = f"UPDATE {DB_TABLE} SET {update_values[:-2]} WHERE document_id = '{document_qr_decode['document_id']}' AND hashedDocumentName = '{document_qr_decode['hashedDocumentName']}'"
    logger.info(f'## Query to update row : {query}')
    return query

def find_document_qr_decode(data: dict) -> dict:
    query = f"SELECT * FROM {DB_TABLE} WHERE document_id = '{data['document_id']}' AND hashedDocumentName = '{data['hashedDocumentName']}'"
    logger.info(f'## Query to find document : {query}')
    cnx = mysql.connector.connect(**DB_CONFIG)
    with cnx.cursor(dictionary=True) as cursor:
        cursor.execute(query)
        document_qr_decode = cursor.fetchone()
    cnx.close()
    return document_qr_decode

def update_to_db(document_qr_decode: dict) -> None:  
    cnx = mysql.connector.connect(**DB_CONFIG)
    with cnx.cursor() as cursor:
        cursor.execute(get_sql_update(document_qr_decode))
    cnx.commit()
    cnx.close()
    
def interpret_qr_code(qr: list, document_qr_decode: dict) -> dict:
    for code in qr:
        logger.info(f'## First image decoded')
        data_list = code.data.decode('UTF-8').split(' ')
        if is_valid_document_data(data_list):
            document_qr_decode.update({
                'decoded': 1, 
                'decodedAt': get_datetime_now(),
                'documentTypeLetters': data_list[0], 
                'reference': data_list[1],
                'entityLetter': data_list[2]
            })
        elif is_valid_document_reference(data_list):
            document_qr_decode.update({
                'decoded': 1,
                'decodedAt': get_datetime_now(),
                'reference': data_list[0]
            })
    return document_qr_decode    

def get_datetime_now() -> str:
    return datetime.now().astimezone(pytz.timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")

def decode_process(image: Image, document_qr_decode: dict) -> dict:
    logger.info(f'## Check first image to decode')
    qr = decode(image)
    if len(qr) > 0:
        document_qr_decode = interpret_qr_code(qr, document_qr_decode)

    if 0 == document_qr_decode['decoded']:
        logger.info(f'## First image not decoded')
        document_qr_decode.update({
            'decoded': 1,
            'decodedAt': get_datetime_now(),
        })
    else:
        logger.info('## Document decoded')
                
    image.close()
    return document_qr_decode

# Method used by AWS Lambda
def handler(event, context):
    logger.info('## Start lambda function')
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote_plus(event['Records'][0]['s3']['object']['key'])
    logger.info(f'## Handle document with key : {key}')
    # Get the document name from the S3 key
    doc_name = key.split('/')[-1]
    data = {
        'document_id': doc_name.split('-')[0],
        'hashedDocumentName': doc_name,
    }
    document_qr_decode = find_document_qr_decode(data)
    if document_qr_decode['decoded'] == 1 :
        logger.info(f"## Document ID {document_qr_decode['document_id']} already decoded")
        return {
            'statusCode': 200,
            'body': json.dumps(document_qr_decode, default=str)
        }
    try: 
        # Download the file from S3 to temp name
        temp = '/tmp/{}'.format(str(time.time()))
        to_decode = True
        logger.info(f'## Download S3 file at tmp path : {temp}')
        S3.download_file(bucket, key, temp)
        # Convert the file to img to use the decode
        logger.info('## Convert file to img')
        try:
            with tempfile.TemporaryDirectory() as path:
                images_from_path = convert_from_path(temp, output_folder=path, first_page=1, last_page =1)
        except PDFPageCountError as e:
            try: 
                logger.info('## Try to open the file as an image')
                images_from_path = [Image.open(temp)]
            except Exception as e:
                to_decode = False

        if to_decode:
            decode_process(images_from_path[0], document_qr_decode)
        else:
            logger.info('## No image to decode')
            raise Exception('No image to decode')
    except Exception as e:
        logger.error(f'## Error : {e}')
        document_qr_decode.update({
            'decoded': 1,
            'decodedAt': get_datetime_now(),
        })
    finally:
        os.remove(temp)        
        logger.info('## Update to DB : %s', document_qr_decode)
        document_qr_decode.update({'updatedAt': get_datetime_now()})
        update_to_db(document_qr_decode)
        return {
            'statusCode': 200,
            'body': json.dumps(document_qr_decode, default=str)
        }
