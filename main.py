import os
import tempfile
from remove_bg_util import *
from fastapi import FastAPI, UploadFile
from ultralytics import YOLO
from PIL import Image
from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
import shutil
from pathlib import Path
import logging
import python_weather
from recom_screenshot import RecOutfit
from fastapi.responses import FileResponse
from fastapi import File, Form
import pandas as pd
from datetime import datetime
import uuid



# Configure the logger
logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")


# Create a FastAPI application
app = FastAPI(debug=True,title='Fashion AI',summary='This API Provides Access to all Endpoints of Fashion AI Server')

def extract(source_path):
    model = YOLO("model//best.pt")
    results=model.predict(source=source_path, conf=0.4, save=False, line_width=2)
    class_names=['sunglass','hat','jacket','shirt','pants','shorts','skirt','dress','bag','shoe']

    source = Image.open(source_path)
    items_list=[]
    # Iterate through the detected items and save each one as a separate image
    for item in results:
        # Extract the bounding box coordinates
        x_min, y_min, x_max, y_max = item.boxes.xyxy[0]
        # Crop and save the detected item as a separate image
        detected_item = source.crop((float(x_min), float(y_min), float(x_max), float(y_max)))
        if class_names[int(item.boxes.cls.tolist()[0])].lower() not in ['sunglass','hat','bag']:
            items_list.append({class_names[int(item.boxes.cls.tolist()[0])]:detected_item})  
    return items_list

# Define a route to process images and remove the background
def remove_bg(img):
    print('inside')
    # Remove the image background using the "rembg" library
    removedBGimage = remove(img, True)
    print('removing')

    # Automatically crop the image
    croppedImage = autocrop_image(removedBGimage, 0)
    print('croping')
    # Resize the cropped image to a specific size (700 pixels in this case)
    resizedImage = resize_image(croppedImage, 700)
    print('resizing')
    # Create a new canvas with a specific size (1000x1000) and paste the image onto it
    combinedImage = resize_canvas(resizedImage, 1000, 1000)
    print('resizing canvas')
    return combinedImage

 
# Define an endpoint to receive and save the image
@app.post("/remove_background/")
async def remove_background(file: UploadFile):
    try:
        # Create a directory to save the uploaded files if it doesn't exist
        upload_dir = Path("temp")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save the uploaded file to the local directory
        with open(upload_dir / file.filename, "wb") as image_file:
            shutil.copyfileobj(file.file, image_file)
        
        print('going in')
        image=remove_bg(Image.open(upload_dir / file.filename))
        print('bg removed')
        shutil.rmtree('temp',ignore_errors=True)
          # Save the PIL Image as JPEG in a temporary file
        with BytesIO() as temp_buffer:
            image.save(temp_buffer, format="PNG")
            temp_buffer.seek(0)
            
            # Create a temporary file and write the image data to it
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                temp_file.write(temp_buffer.read())
                temp_file_path = temp_file.name
        print('returning')
        return FileResponse(temp_file_path, media_type="image/jpeg", headers={"Content-Disposition": "attachment; filename=removed.png"})

    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

# Define an endpoint to receive and save the image
@app.post("/extract/")
async def upload_file(file: UploadFile):
    try:
        # Create a directory to save the uploaded files if it doesn't exist
        upload_dir = Path("temp")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save the uploaded file to the local directory
        with open(upload_dir / file.filename, "wb") as image_file:
            shutil.copyfileobj(file.file, image_file)
            
        items_list=extract(upload_dir / file.filename)
        images_list=[]
        for item in items_list:
            image_name=list(item.keys())[0]
            image=list(item.values())[0]
            image=remove_bg(image)
            image.save('{}.png'.format(image_name))
            logging.info(image_name)
            images_list.append({'name':image_name,'image':'image'}) # i want to return this image 
        
        shutil.rmtree('temp',ignore_errors=True)
        return JSONResponse(content={"message": images_list})
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
    
    
    
    
# Define an endpoint to receive and save the image
@app.get("/getweather/{area}")
async def getweather(area):
  # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
  async with python_weather.Client(unit=python_weather.IMPERIAL) as client:
    # fetch a weather forecast from a city
    weather = await client.get(area)
    
    temperature=weather.current.temperature
    temperature = (temperature - 32) * 5/9
    if temperature<25:
        season='winter'
        
    else:
        season='summer'

    return JSONResponse(content={"temperature": temperature,"season":season,'description':weather.current.description,'kind':str(weather.current.kind)})




@app.post('/get_recommendation')
async def get_recommendations(file: UploadFile,Gender,Ocassion,Season):
    
    # Create a directory to save the uploaded files if it doesn't exist
    upload_dir = Path("temp")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save the uploaded file to the local directory
    with open(upload_dir / file.filename, "wb") as image_file:
        shutil.copyfileobj(file.file, image_file)
        
        
    
    
    input_image={'image_path':upload_dir / file.filename,'Image Tags':{'Gender':Gender.lower(),'Season':Season.lower(),'Occasion':Ocassion.lower()}}
    print(input_image)
    recoutfit=RecOutfit(input_image,'Wardrobe')
    recommended_outfit,image=recoutfit.controller()
   
    # Save the PIL Image as JPEG in a temporary file
    with BytesIO() as temp_buffer:
        image.save(temp_buffer, format="JPEG")
        temp_buffer.seek(0)
        
        # Create a temporary file and write the image data to it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(temp_buffer.read())
            temp_file_path = temp_file.name
    return FileResponse(temp_file_path, media_type="image/jpeg", headers={"Content-Disposition": "attachment; filename=recommended.png"})


@app.post('/get_recommendations_collage')
async def get_recommendations_collage(file: UploadFile,Gender,Ocassion,Season):
    
    # Create a directory to save the uploaded files if it doesn't exist
    upload_dir = Path("temp")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save the uploaded file to the local directory
    with open(upload_dir / file.filename, "wb") as image_file:
        shutil.copyfileobj(file.file, image_file)

    items_list=extract(upload_dir / file.filename)
    images_list=[]
    for item in items_list:
        image_name=list(item.keys())[0]
        image=list(item.values())[0]
        image=remove_bg(image)
        image.save('temp.png')
        
        input_image={'image_path':upload_dir / file.filename,'Image Tags':{'Gender':Gender.lower(),'Season':Season.lower(),'Occasion':Ocassion.lower()}}
        print(input_image)
        recoutfit=RecOutfit(input_image,'Wardrobe')
        recommended_outfit,rec_image=recoutfit.controller()
        images_list.append(rec_image)

    try:
        os.remove('temp.png')
    except:
        pass
    print(images_list[0])
    total_width = sum([img.width for img in images_list])
    max_height = max([img.height for img in images_list])
    collage = Image.new("RGB", (total_width, max_height))
    x_offset = 0  # Starting position for the first image
    for img in images_list:
        collage.paste(img, (x_offset, 0))
        x_offset += img.width
    with BytesIO() as temp_buffer:
        collage.save(temp_buffer, format="JPEG")
        temp_buffer.seek(0)
    
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(temp_buffer.read())
            temp_file_path = temp_file.name
    return FileResponse(temp_file_path, media_type="image/jpeg", headers={"Content-Disposition": "attachment; filename=recommended.png"})

@app.get("/")
async def root():
    return {"message": "Welcome to the Fashion AI API! Use /docs for API documentation."}

@app.post("/add_to_wardrobe/")
async def add_to_wardrobe(
    file: UploadFile = File(...),
    gender: str = Form(...),
    season: str = Form(...),
    occasion: str = Form(...)
):
    try:
        wardrobe_dir = Path("Wardrobe")
        wardrobe_dir.mkdir(parents=True, exist_ok=True)
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        save_path = wardrobe_dir / unique_filename
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        new_entry = {
            "image_id": unique_filename,
            "Gender": gender.strip().lower(),
            "Season": season.strip().lower(),
            "Occasion": occasion.strip().lower(),
            "Date_Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        excel_path = "FashionAI Data.xlsx"
        try:
            df = pd.read_excel(excel_path)
        except FileNotFoundError:
            df = pd.DataFrame(columns=["image_id", "Gender", "Season", "Occasion", "Date_Added"])
        df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        df.to_excel(excel_path, index=False)

        return JSONResponse(
            content={"message": "Item added to wardrobe successfully", "filename": unique_filename},
            status_code=201
        )

    except Exception as e:
        logging.error(f"Error adding to wardrobe: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to add item: {str(e)}"},
            status_code=500
        )
    
import random
from colorthief import ColorThief

@app.post('/get_outfit_suggestion')
async def get_outfit_suggestion(Gender: str, Occasion: str, Season: str, color: str = None):
    try:
        # 1. Load wardrobe metadata
        wardrobe_dir = Path("Wardrobe")
        tags_df = pd.read_excel('FashionAI Data.xlsx')
        tags_df = tags_df.apply(lambda x: x.str.lower() if x.dtype == "object" else x)
        
        # 2. Filter by parameters
        filtered = tags_df[
            (tags_df['Gender'] == Gender.lower()) &
            (tags_df['Occasion'] == Occasion.lower()) &
            (tags_df['Season'] == Season.lower())
        ]
        
        if filtered.empty:
            return JSONResponse(content={"error": "No matching items found for the given criteria"}, status_code=404)
        
        # 3. Categories we want to include in the outfit
        categories = {
            'top': ['shirt', 'jacket', 'dress'],
            'bottom': ['pants', 'shorts', 'skirt'],
            'shoe': ['shoe']
        }
        
        # Use the YOLO model to identify item types
        model = YOLO("model//best.pt")
        outfit_items = []
        
        # Process each item from filtered dataframe
        for _, row in filtered.iterrows():
            image_path = wardrobe_dir / row['image_id']
            
            # Use YOLO to detect the item type
            results = model.predict(source=str(image_path), conf=0.4, save=False)
            if not results or len(results) == 0:
                continue
                
            # Get the predicted class
            class_names=['sunglass','hat','jacket','shirt','pants','shorts','skirt','dress','bag','shoe']
            detected_classes = [class_names[int(box.cls.item())] for box in results[0].boxes]
            
            # If there are multiple detections, take the one with highest confidence
            detected_class = detected_classes[0] if detected_classes else None
            
            if not detected_class:
                continue
            
            # Find which category this item belongs to
            item_category = None
            for category, types in categories.items():
                if detected_class in types:
                    item_category = category
                    break
            
            if item_category:
                # Check if we already have an item for this category
                category_exists = any(item[1] == item_category for item in outfit_items)
                
                # If we don't have this category yet, add it
                if not category_exists:
                    outfit_items.append((image_path, item_category, detected_class))
        # Create outfit collage
        images = [Image.open(str(item[0])) for item in outfit_items]
        
        # Process each image to remove background
        processed_images = []
        for img in images:
            # Remove background using your existing function
            processed_img = remove_bg(img)
            processed_images.append(processed_img)
        
        # Create a collage
        total_width = sum([img.width for img in processed_images])
        max_height = max([img.height for img in processed_images])
        
        # Ensure reasonable dimensions
        scale_factor = min(1.0, 1200 / total_width) if total_width > 0 else 1.0
        new_width = int(total_width * scale_factor)
        new_height = int(max_height * scale_factor)
        
        collage = Image.new("RGB", (new_width, new_height), color=(255, 255, 255))
        x_offset = 0
        
        for img in processed_images:
            # Scale image
            new_img_width = int(img.width * scale_factor)
            new_img_height = int(img.height * scale_factor)
            resized_img = img.resize((new_img_width, new_img_height), Image.LANCZOS)
            
            # Paste into collage
            collage.paste(resized_img, (x_offset, 0), resized_img if resized_img.mode == 'RGBA' else None)
            x_offset += new_img_width
        
        # Return image response
        with BytesIO() as temp_buffer:
            collage.save(temp_buffer, format="JPEG")
            temp_buffer.seek(0)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                temp_file.write(temp_buffer.read())
                temp_file_path = temp_file.name
                
        return FileResponse(
            temp_file_path, 
            media_type="image/jpeg", 
            headers={"Content-Disposition": "attachment; filename=outfit_suggestion.jpg"}
        )
        
    except Exception as e:
        logging.error(f"Outfit suggestion error: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)