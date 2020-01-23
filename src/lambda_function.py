import boto3
import logging
import os
import shutil
import stat
import subprocess
import json

s3_client = boto3.client('s3')
trans_client = boto3.client('transcribe')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

lambda_tmp_dir = '/tmp'  # Lambda fuction can use this directory.


def is_lambda_runtime():
    return True if "LAMBDA_TASK_ROOT" in os.environ else False


if is_lambda_runtime():
    # ffmpeg is stored with this script.
    # When executing ffmpeg, execute permission is requierd.
    # But Lambda source directory do not have permission to change it.
    # So move ffmpeg binary to `/tmp` and add permission.
    ffmpeg_bin = "{0}/ffmpeg.linux64".format(lambda_tmp_dir)
    shutil.copyfile('/var/task/ffmpeg.linux64', ffmpeg_bin)
    os.environ['IMAGEIO_FFMPEG_EXE'] = ffmpeg_bin
    os.chmod(ffmpeg_bin, os.stat(ffmpeg_bin).st_mode | stat.S_IEXEC)


def lambda_handler(event, context):
    print(json.dumps(event))
    for r in event['Records']:
        s3 = r['s3']
        bucket = s3['bucket']['name']
        key = s3['object']['key']
        ff = os.path.split(key)
        split = os.path.split(key)
        if split[0] == 'raw':
            source = download_audio(bucket, key)
            output = os.path.splitext(source)[0] + '.mp3'
            transcode_audio(source, output)
            output_key = os.path.join('transcoded', split[1])
            output_key = os.path.splitext(output_key)[0] + '.mp3'
            s3_client.upload_file(output, bucket, output_key)
        elif split[0] == 'transcoded':

            response = trans_client.start_transcription_job(
                TranscriptionJobName=split[1],
                LanguageCode='en-US',
                Media={
                    'MediaFileUri': 's3://rhunter-audio/{}'.format(key)
                }
            )
            ## execute transcription
            pass


    logger.info("{0} records processed.".format(len(event['Records'])))
    return True


def download_audio(bucket, key):
    local_source_audio = lambda_tmp_dir + "/" + key
    directory = os.path.dirname(local_source_audio)
    if not os.path.exists(directory):
        os.makedirs(directory)

    s3_client.download_file(bucket, key, local_source_audio)
    output = subprocess.check_output(["file", local_source_audio])
    logger.debug("Audio file downloaded to {}".format(str(output, "utf-8")))
    return local_source_audio


def transcode_audio(local_source_audio, output_file):
    logger.debug('start transcode_audio()')
    resp = subprocess.check_output([ffmpeg_bin, '-i', local_source_audio, '-vn', '-acodec', 'mp3', '-ar', '16000', '-y', output_file])
    logger.debug(str(resp, "utf-8"))
    logger.debug(str(subprocess.check_output(["file", output_file]), "utf-8"))


def upload_mp3(bucket, output):
    logger.debug('uploading to S3 bucket: {}, key: {}'.format(bucket, output))
