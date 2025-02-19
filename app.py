import random
import string
from typing import Union
from bson import ObjectId
from flask import Flask, redirect,render_template,jsonify,request,send_file, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
from github import Github
from github import Auth
from PIL import Image
import hashlib
import secrets
import jwt
import os

load_dotenv(override=True)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")
SECRET_KEY = os.environ.get("SECRET_KEY")
SALT_HASH = os.environ.get("SALT_HASH")
GH_USER = os.environ.get("GH_USER")
GH_PW = os.environ.get("GH_PW")
GH_TOKEN = os.environ.get("GH_TOKEN")
TOKEN = 'token'

IMAGES_THUMBNAIL_SIZE = (300,300)

# using an access token
StorageRepo = "ambatron-dev/storage-ukk"
StorageURL = "https://ambatron-dev.github.io/storage-ukk/"
# Default foto profil untuk user
default_profile_pic = "./static/defaults/default-profile-pic.png"

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
# app.config['PROFILE'] = './static/profile_pics'
# app.config['PHOTOS'] = './static/photos'

# MongoDB
client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
# Collection
table_users = db.users
table_photos = db.photos

# JWT Token exp
Expired_Seconds = 60 * 60 * 24 # 24 Hour / 86400 seconds
allowed_ext = {'png', 'jpg', 'jpeg', 'gif'}
# Filter extensi file yang diterima
def check_ext(extension:str):
    # Cek dengan ekstensi yg boleh
    return True if extension in allowed_ext else False

# Login ke github dengan token yang didapat dari github settings developer
def login_github():
    auth = Auth.Token(token=GH_TOKEN)
    return Github(auth=auth)

# Upload file ke github atau update
def upload_file_or_update(path:str,message:str,content:Union[str,bytes],update=False,branch:str="main"):
    g = login_github()
    repo = g.get_repo(StorageRepo)
    if update:
        contents = repo.get_contents(path)
        repo.update_file(path=contents.path, message=message, content=content, sha=contents.sha, branch=branch)
    else:
        repo.create_file(path=path,message=message,content=content,branch=branch)
    g.close()

# Delete file github storage
def delete_file_from_storage(path:str,message:str,branch:str="main"):
    g = login_github()
    repo = g.get_repo(StorageRepo)
    contents = repo.get_contents(path)
    repo.delete_file(path=contents.path, message=message, sha=contents.sha, branch=branch)
    g.close()

# Generate thumbnail
def generate_thumbnail(input_image_path, output_thumbnail_path, thumbnail_size=(300, 300)):
    try:
        # Open the image file
        image = Image.open(input_image_path)
        # Generate the thumbnail
        image.thumbnail(thumbnail_size)
        # Save the thumbnail to the output path
        image.save(output_thumbnail_path)
        print(f"Thumbnail generated and saved to '{output_thumbnail_path}'")
    except Exception as e:
        print("Error generating thumbnail:", e)

# Jika baru pertama kali menjalankan kita harus cek dulu apakah folder sudah lengkap
def check_folders():
    print("Checking folders ... ")
    check = ["./static/temp/photos","./static/temp/profile_pics"]
    for path in check:
        if not os.path.exists(path=path):
            # Buat folder jika tidak ada
            os.makedirs(name=path)
            
def generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def hash_salt_password(password:str):
    # Hash password
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # Salt password agar lebih aman
    salted_password = SALT_HASH+password_hash
    return salted_password

# Jika database tidak ada user superadmin
def check_superadmin():
    superadmin = table_users.find_one({"is_superadmin":True})
    if not superadmin:
        pw = generate_password(length=31)
        salted_password = hash_salt_password(pw)
        doc = {
            "username":"helios-ruler",
            "password":salted_password,
            "bio": "I'am the ruler of the world",
            "profile_pic": default_profile_pic,
            "gender": "N/A",
            "is_superadmin": True,
        }
        table_users.insert_one(doc)
        print(f"# ------------------ #")
        print(f"# Generated superadmin")
        print(f"# User : helios-ruler")
        print(f"# Password : {pw}")

# -------------- ENDPOINT -------------- #

@app.get("/")
def home():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        # Payload terverifikasi
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    return render_template('index.html')

@app.get("/api/search")
def search():
    query = request.form.get('query', '')
    gallery_data = list(table_photos.find({},{"_id":False}))
    results = []
    for image in gallery_data:
        # Jika title terdapat unsur query
        if query.lower() in image['title'].lower():
            # Tambahkan ke result
            results.append(image)
        # Jika kategori terdapat unsur query
        elif query.lower() in image['kategori'].lower():
            # Tambahkan ke result
            results.append(image)
        # Jika deskripsi terdapat unsur query
        elif query.lower() in image['deskripsi'].lower():
            # Tambahkan ke result
            results.append(image)
        # Jika username terdapat unsur query
        elif query.lower() in image['username'].lower():
            # Tambahkan ke result
            results.append(image)
    return jsonify({"results":results})

@app.get("/about")
def about_page():
    return render_template("about.html")

# Get info dari token tentang user
@app.get("/api/me")
def get_info_me():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload['username']
        # Payload terverifikasi
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    # Exclude password
    user = table_users.find_one({"username":username},{"password":False})
    user["_id"] = str(user["_id"])
    return jsonify({"data":user})

# Update user info, bio, gender ...
@app.put("/api/me")
def update_info_me():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload['username']
        # Payload terverifikasi
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    bio_receive = request.form.get('bio_give')
    gender_receive = request.form.get('gender_give')
    new_doc = {
        "bio": bio_receive,
        "gender": gender_receive,
    }
    table_users.update_one({"username":username},{"$set":new_doc})
    return jsonify({"msg":"Item updated"})
    
# Endpoint ambil path images
@app.get("/api/images") # Optional args skip and limit, contoh : /api/images?skip=0&limit=10
def get_images():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        # Payload terverifikasi
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    skip = int(request.args.get("skip",default=0))
    limit = int(request.args.get("limit",default=20))
    # Sort dari id terbaru (-1) jika (1) maka dari yang terdahulu
    photos = list(table_photos.find({}).sort("_id",-1).skip(skip=skip).limit(limit=limit))
    idx = 0
    for doc in photos:
        photos[idx]["_id"] = str(doc["_id"])
        idx += 1
    return jsonify({"data":photos})

# Endpoint ambil path images by me
@app.get("/api/images/me") # Optional args skip and limit, contoh : /api/images?skip=0&limit=10
def get_images_me():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload["username"]
        # Payload terverifikasi
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    skip = int(request.args.get("skip",default=0))
    limit = int(request.args.get("limit",default=20))
    # Sort dari id terbaru (-1) jika (1) maka dari yang terdahulu
    photos = list(table_photos.find({"username":username}).sort("_id",-1).skip(skip=skip).limit(limit=limit))
    idx = 0
    for doc in photos:
        photos[idx]["_id"] = str(doc["_id"])
        idx += 1
    return jsonify({"data":photos})

# Endpoint tambah foto
@app.post("/api/images/create")
def create_images():
    # Ambil cookie file
    token_receive = request.cookies.get(TOKEN)
    try:
        # Lihat isi cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload['username']
        # Payload terverifikasi
        pass
    except (jwt.ExpiredSignatureError,jwt.exceptions.DecodeError):
        # Tidak ada token atau belum login
        return redirect(url_for('home'))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    # Cek jika file telah terupload
    if 'file_give' in request.files:
        file = request.files['file_give']
        title_receive = request.form.get("title_give","")
        deskripsi_receive = request.form.get("deskripsi_give","")
        kategori_receive = request.form.get("kategori_give","")

        # Amankan filename dari karakter spesial
        filename = secure_filename(file.filename)
        extension = os.path.splitext(filename)[-1].replace('.','')
        if not check_ext(extension):
            return jsonify({"msg":"Extension not allowed"}),406 # Not acceptable
        unique_format = f"{username}-{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        file_path = f"photos/{unique_format}"
        file_save_path = f"./static/temp/{file_path}"

        # Cek apakah folder tersedia
        check_folders()
        # Simpan file ke folder temp
        file.save(file_save_path)

        # Thumbnail
        thumbnail_unique_format = f"thumbnail_{unique_format}"
        thumbnail_path = f"photos/{thumbnail_unique_format}"
        file_save_path_thumbnail = f"./static/temp/{thumbnail_path}"
        generate_thumbnail(input_image_path=file_save_path,output_thumbnail_path=file_save_path_thumbnail,thumbnail_size=IMAGES_THUMBNAIL_SIZE)
        
        # Open file sebagai binary
        with open(file_save_path, "rb") as image:
            f = image.read()
            image_data = bytearray(f)
            # Upload ke github storage
            upload_file_or_update(file_path,f"By {username}",bytes(image_data))

        # Open file sebagai binary
        with open(file_save_path_thumbnail, "rb") as image:
            f = image.read()
            image_data = bytearray(f)
            # Upload ke github storage
            upload_file_or_update(thumbnail_path,f"By {username}",bytes(image_data))

        # Delete temp file
        os.remove(file_save_path)
        os.remove(file_save_path_thumbnail)
        doc = {
            "username": username,
            "image": StorageURL+file_path,
            "image_repo": file_path,
            "image_thumbnail": StorageURL+thumbnail_path,
            "image_thumbnail_repo": thumbnail_path,
            "title_receive": title_receive,
            "deskripsi_receive": deskripsi_receive,
            "kategori_receive": kategori_receive,
        }
        # Masukkan url ke database
        table_photos.insert_one(doc)
        return {"msg":"Photo uploaded"}
    else:
        # Foto tidak terupload
        return {"msg":"No image uploaded"},404 # Not found

# Endpoint delete foto
@app.delete("/api/images/delete")
def delete_images():
    # Ambil cookie file
    token_receive = request.cookies.get(TOKEN)
    try:
        # Lihat isi cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload['username']
        is_superadmin = payload['is_superadmin']
        # Payload terverifikasi
        pass
    except (jwt.ExpiredSignatureError,jwt.exceptions.DecodeError):
        # Tidak ada token atau belum login
        return redirect(url_for('home'))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    image_id = request.form.get("image_id_give")
    # Ambil data dari database
    result = table_photos.find_one({"_id":ObjectId(image_id)})
    if not result:
        return jsonify({"msg":"Image not found"}),404 # Not found
    if is_superadmin:
        # Jika superadmin maka bolehkan
        pass
    # Jika owner foto tersebut berbeda maka tidak akan di hapus
    elif result.get("username") != username:
        return jsonify({"msg":"Image owner is different"}),403 # Forbidden
    # Delete dari github storage
    delete_file_from_storage(result.get("image_repo"),f"Delete By {username}")
    delete_file_from_storage(result.get("image_thumbnail_repo"),f"Delete By {username}")
    # Delete dari mongodb
    table_photos.delete_one({"_id":ObjectId(image_id)})
    return jsonify({"msg":"Image deleted"})

# Endpoint update foto profil
@app.put("/api/profile/image")
def update_profile_image():
    # Ambil cookie
    token_receive = request.cookies.get(TOKEN)
    try:
        # Buka konten cookie
        payload = jwt.decode(token_receive,SECRET_KEY,algorithms=['HS256'])
        username = payload["username"]
        pass
    except jwt.ExpiredSignatureError:
        # Sesinya sudah lewat dari 24 Jam
        msg = 'Your session has expired'
        return redirect(url_for('login_fn',msg=msg))
    except jwt.exceptions.DecodeError:
        # Tidak ada token
        msg = 'Something wrong happens'
        return redirect(url_for('login_fn',msg=msg))
    # Jika payload terverifikasi maka kode dibawah akan di execute
    # Cek jika file telah terupload
    if 'file_give' in request.files:
        file = request.files['file_give']
        # Amankan filename dari karakter spesial
        filename = secure_filename(file.filename)
        extension = os.path.splitext(filename)[-1].replace('.','')
        
        if not check_ext(extension):
            return jsonify({"msg":"Extension not allowed"}),406 # Not acceptable
        
        # Get current user profile pic
        current_data = table_users.find_one({"username":username},{"_id":False})
        current_data_profile_pic = current_data.get("profile_pic_repo")
        
        unique_format = f"{username}-{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.{extension}"
        file_path = f"profile_pics/{unique_format}"
        file_save_path = f"./static/temp/{file_path}"
        # Cek apakah folder tersedia
        check_folders()
        # Simpan file ke folder temp
        file.save(file_save_path)
        
        # Cek apakah user pernah mengupload file ke storage
        if current_data_profile_pic:
            # Delete dari storage
            delete_file_from_storage(current_data_profile_pic,f"Delete By {username}")
        else:
            # Maka user masih menggunakan profile pict default dari static folder
            pass
        # Open file sebagai binary
        with open(file_save_path, "rb") as image:
            f = image.read()
            image_data = bytearray(f)
            # Upload ke github storage
            upload_file_or_update(file_path,f"By {username}",bytes(image_data))
        # Delete temp file
        os.remove(file_save_path)
        doc = {"profile_pic": StorageURL+file_path,"profile_pic_repo":file_path}
        # Masukkan url ke database
        # $set adalah cara mongodb mengupdate suatu document dalam table
        table_users.update_one(filter={"username":username},update={"$set":doc})
        return {"msg":"Photo uploaded"}
    else:
        # Foto tidak terupload
        return {"msg":"No image uploaded"},404 # Not found

# Login page
@app.get("/login")
def login_fn():
    msg = request.args.get("msg")
    return render_template("login.html", msg=msg)

# Endpoint registrasi
@app.post('/api/sign_up')
def sign_up():
    username_receive = request.form.get('username_give')
    password_receive = request.form.get('password_give')
    # Cek apakah username telah dipakai
    user_from_db = table_users.find_one({"username":username_receive})
    if user_from_db:
        return jsonify({"msg":"username telah dipakai"}),409 # Conflict
    salted_password = hash_salt_password(password_receive)
    doc = {
        "username": username_receive,
        "password": salted_password,
        "bio": "Hello this is my bio",
        "profile_pic": default_profile_pic,
        "gender": "N/A",
        "is_superadmin": False,
    }
    # Masukkan ke database
    table_users.insert_one(doc)
    return jsonify({'result':'success'})

# Sign in untuk mendapat token JWT
@app.post("/api/sign_in")
def sign_in():
    username_receive = request.form.get('username_give')
    password_receive = request.form.get('password_give')
    # Mencari user dengan username tsb
    user_from_db = table_users.find_one({"username":username_receive})
    salted_password = hash_salt_password(password_receive)
    # Compare digest digunakan untuk mencegah timing attack
    is_correct_username = secrets.compare_digest(user_from_db.get("username"), username_receive)
    is_correct_password = secrets.compare_digest(user_from_db.get("password"), salted_password)
    if not is_correct_username or not is_correct_password:
        # Login salah
        return jsonify({
            "result":"fail", "msg":"Cannot find user with that username and password combination",
        }),404 # Not found
    # Buat isi token
    payload={
        "is_superadmin":user_from_db.get("is_superadmin"),
        "username":user_from_db.get("username"),
        "exp": datetime.now() + timedelta (seconds=Expired_Seconds),
    }
    # Buat token lalu encode
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return jsonify({"result": "success","token": token})

if __name__ == "__main__":
    check_superadmin()
    app.run("0.0.0.0",5000,True)