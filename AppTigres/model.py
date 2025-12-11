import google.generativeai as genai
import os
from dotenv import load_dotenv


load_dotenv()


api_key = "AIzaSyCNMH0akbwwhI_tqeB7V6wEwANas7HzXR0"

if not api_key:
    print("Error: No se encontró la API Key.")
else:
    genai.configure(api_key=api_key)
    print("--- MODELOS DISPONIBLES PARA TI ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Nombre: {m.name}")
    except Exception as e:
        print(f"Error conectando: {e}")