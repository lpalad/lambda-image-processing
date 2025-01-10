

import json
import boto3
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import os

# Initialize AWS services
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ImageMetadata')

def lambda_handler(event, context):
    print("Lambda function started")
    print("Received event:", json.dumps(event))
    
    try:
        # Handle S3 trigger event
        if 'Records' in event and event['Records'][0]['eventSource'] == 'aws:s3':
            record = event['Records'][0]['s3']
            bucket = record['bucket']['name']
            key = record['object']['key']
            print(f"Triggered by S3 event - Bucket: {bucket}, Key: {key}")
        else:
            bucket = 's3-lambda-1735992190'
            key = event.get("key", "unknown.jpg")
            print(f"Direct invocation - Key: {key}")

        # Get the image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        original_size = len(image_data)

        # Open the image
        image = Image.open(io.BytesIO(image_data))
        
        # Add watermark
        if image.mode in ('RGBA', 'LA'):
            image = image.convert('RGB')
            
        # Create drawing object
        draw = ImageDraw.Draw(image)
        
        # Add watermark text
        width, height = image.size
        text = "© MyService 2025"
        x = width - (width / 4)
        y = height - (height / 5)
        
        # Add white text with black outline
        draw.text((x, y), text, 
                 fill='white',
                 stroke_width=5,
                 stroke_fill='black')

        # Save processed image
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=60, optimize=True)
        buffer.seek(0)
        processed_data = buffer.getvalue()
        processed_size = len(processed_data)

        # Generate new key in processed folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        processed_key = f"processed/{timestamp}.jpg"

        # Upload processed image
        print(f"Uploading processed image to: {processed_key}")
        s3.put_object(
            Bucket=bucket,
            Key=processed_key,
            Body=processed_data,
            ContentType='image/jpeg'
        )

        # Calculate compression ratio
        compression_ratio = ((original_size - processed_size) / original_size) * 100

        # Save metadata to DynamoDB
        table.put_item(
            Item={
                "ImageID": processed_key,
                "OriginalKey": key,
                "Status": "Processed",
                "Timestamp": datetime.now().isoformat(),
                "RequestID": context.aws_request_id,
                "OriginalSize": original_size,
                "ProcessedSize": processed_size,
                "CompressionRatio": f"{compression_ratio:.2f}%"
            }
        )

        print(f"Processing completed. Compression ratio: {compression_ratio:.2f}%")
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "message": "Image processed successfully",
                "original_key": key,
                "processed_key": processed_key,
                "compression_ratio": f"{compression_ratio:.2f}%"
            })
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "message": f"Error processing image: {str(e)}"
            })
        }

