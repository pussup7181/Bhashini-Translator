from flask import Flask, request, jsonify, render_template
import requests
import base64
from pydub import AudioSegment
from io import BytesIO
import os

app = Flask(__name__)

# Load environment variables
USER_ID = os.getenv('USER_ID')
API_KEY = os.getenv('API_KEY')
PIPELINE_ID = os.getenv('PIPELINE_ID')

# Configuration variables
ulca_base_url = 'https://meity-auth.ulcacontrib.org'
model_pipeline_endpoint = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"

# Function to convert base64 string back to audio file
def base64_to_audio(base64_string):
    audio_data = base64.b64decode(base64_string)
    audio = AudioSegment.from_file(BytesIO(audio_data), format="wav")
    return audio

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_audio', methods=['POST'])
def process_audio():
    try:
        data = request.json
        audio_base64 = data['audio']
        source_lang = data['sourceLang']
        target_lang = data['targetLang']
        
        # Step 1: Send request to get pipeline details
        response = requests.post(
            model_pipeline_endpoint,
            json={
                "pipelineTasks": [
                        {
                            "taskType": "asr",
                            "config": {
                                "language": {
                                    "sourceLanguage":source_lang
                                }
                            }
                        },
                        {
                            "taskType": "translation",
                            "config": {
                                "language": {
                                    "sourceLanguage": source_lang,
                                    "targetLanguage": target_lang
                                }
                            }
                        },
                        {
                            "taskType": "tts",
                            "config": {
                                "language": {
                                    "sourceLanguage": target_lang
                                }
                            }
                        }
                    ],
                    "pipelineRequestConfig": {
                        "pipelineId": PIPELINE_ID
                    }
                },
            headers={'Content-Type': 'application/json', 'ulcaApiKey': API_KEY, 'userID': USER_ID}
        )

        if response.status_code != 200:
            print(f"Pipeline request failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to get pipeline details'}), 500

        pipeline_response = response.json()
        callback_url = pipeline_response['pipelineInferenceAPIEndPoint']['callbackUrl']
        asr_service_id = pipeline_response['pipelineResponseConfig'][0]['config'][0]['serviceId']
        nmt_service_id = pipeline_response['pipelineResponseConfig'][1]['config'][0]['serviceId']
        tts_service_id = pipeline_response['pipelineResponseConfig'][2]['config'][0]['serviceId']
        compute_authorization_key = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['name']
        compute_call_authorization_value = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['value']
        print(asr_service_id)
        print(f"Callback URL: {callback_url}")
        print(f"Authorization Key: {compute_authorization_key}, Authorization Value: {compute_call_authorization_value}")

        # Step 2: Send audio data for processing
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang
                        },
                        "serviceId": asr_service_id,
                        "audioFormat": "wav",
                        "samplingRate": 16000
                    }
                },
                {
            "taskType": "translation",
            "config": {
                "language": {
                    "sourceLanguage": source_lang,
                    "targetLanguage": target_lang
                },
                "serviceId": nmt_service_id
            }
        },
        {
            "taskType": "tts",
            "config": {
                "language": {
                    "sourceLanguage": target_lang
                },
                "serviceId": tts_service_id,
                "gender": "female",
                "samplingRate": 8000
            }
        }
    ],
    "inputData": {
        "audio": [
            {
                "audioContent":  audio_base64
                    }
                ]
            }
        }

        response = requests.post(
            callback_url,
            json=payload,
            headers={'Content-Type': 'application/json', 'ulcaApiKey': API_KEY, 'userID': USER_ID, compute_authorization_key: compute_call_authorization_value}
        )
        print(f"Response: {response.json()}")

        if response.status_code != 200:
            print(f"Audio processing failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to process audio'}), 500

        transcription = response.json()['pipelineResponse'][0]['output'][0]['source']
        translated_audio = response.json()['pipelineResponse'][2]['audio'][0]['audioContent']
        translation = response.json()['pipelineResponse'][1]['output'][0]['target']
        print(f"User: {transcription}")
        print(f"Translation: {translated_audio}")
        return jsonify({'transcription': transcription,'audio': translated_audio, 'translation': translation})

    except Exception as e:
        print(f"Exception occurred in ASR: {str(e)}")
        return jsonify({'error': 'An error occurred while processing audio'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
