# 🚗💥 Car Damage AI  
**AI-powered vehicle damage detection from images**

Car Damage AI is a full-stack web application that lets users upload car photos and instantly receive an **AI-generated damage analysis**. The system identifies dents, scratches, cracks, bumper impacts, and other common collision damage. The frontend is deployed on Vercel with a custom domain, and the backend is powered by FastAPI on Render.

🔗 **Live App:** https://autoscansai.com  

---

## ⭐ Features

- 📸 Upload or take a photo of your car  
- 🤖 AI identifies dents, scratches, cracks, and impact zones  
- ⚙️ FastAPI backend for quick image inference  
- 🌐 Frontend hosted on Vercel with custom domain + HTTPS  
- 🔁 Retry logic for Render’s cold start delay  
- 📱 Mobile-optimized UI  
- 🎨 Clean and simple interface built with React + Tailwind  

---

## 🏗️ Tech Stack

### **Frontend**
- React (Vite)  
- Tailwind CSS  
- Vercel deployment  
- Custom domain: `autoscansai.com`

### **Backend**
- FastAPI  
- Uvicorn  
- CORS Middleware enabled  
- Hosted on Render (Free Tier)  
- AI image processing + model inference  

---

## 📂 Project Structure

    car-damage-ai/
    ├── src/
    │   ├── components/
    │   ├── App.jsx
    │   ├── main.jsx
    │   └── styles/
    │
    ├── public/
    ├── README.md
    ├── package.json
    └── vite.config.js

---

## 🚀 Running the Project Locally

### 1. Clone the repository

    git clone https://github.com/<your-username>/car-damage-ai.git
    cd car-damage-ai

### 2. Install dependencies

    npm install

### 3. Create a `.env` file

    VITE_API_BASE_URL=http://127.0.0.1:8000

### 4. Start the development server

    npm run dev

---

## 🖼️ How the AI Works

1. User uploads or takes a car photo  
2. The frontend sends the image → FastAPI backend  
3. AI processes the image and detects damage  
4. Backend responds with:  
   - damage type  
   - confidence levels  
   - analysis summary  
5. UI displays results clearly  

---

## 🛠️ API Endpoint

### **POST /analyze-image**  
Uploads an image and returns a JSON response.

Example (frontend):

    const formData = new FormData();
    formData.append("file", file);

    fetch(`${API_BASE_URL}/analyze-image`, {
      method: "POST",
      body: formData,
    });

---

## 🌍 Deployment Notes

### **Frontend (Vercel)**

- Auto-deploys on pushes to `main`  
- CNAME configured for **autoscansai.com**  
- HTTPS handled by Vercel SSL  

### **Backend (Render)**

- Free tier sleeps after inactivity  
- First request may take 20–40 seconds to wake  
- Extra retry logic recommended on frontend  

### **CORS configured for:**

    https://car-damage-ai.vercel.app
    https://autoscansai.com
    https://www.autoscansai.com

---

## ⚠️ Known Limitations

- 💤 Free Render backend may miss the **first POST request** after sleeping  
- Some mobile browsers compress images differently  
- Heavy images may impact inference speed  

---

## ✨ Future Improvements

- Bounding boxes drawn on analyzed images  
- Multi-angle car damage scoring  
- Cost estimate predictions  
- User accounts + saved history  
- Migration to AWS/GCP backend to remove cold starts  

---

## 👤 Author

**Phillip Lyasota**  
Developer – 2025  
Car Damage AI Project  
