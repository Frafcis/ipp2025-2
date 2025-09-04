# =================================================================================
# APLICACIÓN DE VISIÓN POR COMPUTADOR PARA CONTEO DE OBJETOS - IPP 2025

# Realiza la detección y conteo de objetos en tiempo real o desde un archivo,
# mostrando los resultados en una interfaz gráfica interactiva creada con Tkinter.
# =================================================================================

# --- LIBRERÍAS Y MÓDULOS ---
# Se importan las librerías necesarias para la GUI, el manejo de imágenes y la visión por computador.
import tkinter as tk
from tkinter import Scale, filedialog
from PIL import Image, ImageTk
import cv2

# --- CONSTANTES Y VARIABLES GLOBALES ---
# Define los colores de la interfaz, parámetros de detección y variables
BG_COLOR = "#2E2E2E"
TEXT_COLOR = "#FFFFFF"
BUTTON_COLOR = "#424242"
FRAME_COLOR = "#212121"
MIN_AREA_MANCHA = 200

capture = None
is_camera_running = False
source_image = None

# =================================================================================
# === FUNCIONES DE LÓGICA Y PROCESAMIENTO ===
# =================================================================================

# --- Control de Cámara ---
# Inicia y detiene la captura de video, gestionando el estado de los botones de la GUI.
def control_camara(iniciar=True):
    global capture, is_camera_running
    if iniciar:
        if is_camera_running: return
        for i in [0,1]:
            capture = cv2.VideoCapture(i)
            if capture.isOpened(): break
        if not capture or not capture.isOpened():
            print("ADVERTENCIA: No se pudo acceder a la cámara.")
            return
        is_camera_running = True
        btn_start.config(state="disabled"); btn_stop.config(state="normal"); btn_load.config(state="disabled")
        update_frame()
    else:
        is_camera_running = False
        if capture: capture.release()
        btn_start.config(state="normal"); btn_stop.config(state="disabled"); btn_load.config(state="normal")

# --- Bucle de Video en Tiempo Real ---
# Función recursiva que se ejecuta continuamente para leer frames de la cámara
# y mantener la imagen de video actualizada en la interfaz.
def update_frame():
    global source_image
    if is_camera_running:
        ret, frame = capture.read()
        if ret:
            source_image = cv2.flip(frame, 1)
            process_frame(source_image)
        ventana.after(20, update_frame)

# --- Carga de Imagen Estática ---
# Abre un explorador de archivos para que el usuario seleccione una imagen del disco
def cargar_imagen():
    global source_image
    if is_camera_running: control_camara(iniciar=False)
    path_image = filedialog.askopenfilename(filetypes=[("Archivos de imagen", "*.jpg *.jpeg *.png")])
    if path_image:
        source_image = cv2.imread(path_image)
        if source_image is not None: process_frame(source_image)

# --- Procesamiento de Imagen ---
# Núcleo del programa. Aplica una secuencia de filtros de OpenCV (escala de grises,
# desenfoque, umbralización) para detectar los contornos de los objetos, los filtra
# por área para eliminar ruido y finalmente dibuja los resultados sobre las imágenes.
def process_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, thresholded = cv2.threshold(blurred, slider_umbral.get(), 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    manchas_reales = [c for c in contours if cv2.contourArea(c) > MIN_AREA_MANCHA]
    lbl_conteo.config(text=f"MANCHAS ENCONTRADAS: {len(manchas_reales)}")
    img_entrada_con_resultados = frame.copy()
    img_umbral_con_resultados = cv2.cvtColor(thresholded, cv2.COLOR_GRAY2RGB)
    for i, c in enumerate(manchas_reales):
        cv2.drawContours(img_umbral_con_resultados, [c], -1, (0, 255, 0), 2)
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(img_entrada_con_resultados, (x, y), (x + w, y + h), (0, 255, 0), 2)
        M = cv2.moments(c)
        cX = int(M["m10"] / M["m00"]) if M["m00"] != 0 else x
        cY = int(M["m01"] / M["m00"]) if M["m00"] != 0 else y
        cv2.putText(img_entrada_con_resultados, str(i + 1), (cX - 10, cY + 10), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
        cv2.putText(img_umbral_con_resultados, str(i + 1), (cX - 10, cY + 10), cv2.FONT_HERSHEY_TRIPLEX, 1, (0, 0, 255), 2)
    display_image(img_entrada_con_resultados, lbl_original)
    display_image(img_umbral_con_resultados, lbl_umbralizada)

# --- Visualización de Imagen en GUI ---
# Convierte una imagen de formato OpenCV a un formato compatible con la librería
# Tkinter (a través de Pillow) y la muestra en una etiqueta de la interfaz.
def display_image(img_cv, label):
    h, w = img_cv.shape[:2]
    new_width = 500
    ratio = new_width / float(w)
    dim = (new_width, int(h * ratio))
    img_resized = cv2.resize(img_cv, dim, interpolation=cv2.INTER_AREA)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB if len(img_resized.shape) == 3 else cv2.COLOR_GRAY2RGB)
    img_pil = Image.fromarray(img_rgb)
    img_tk = ImageTk.PhotoImage(image=img_pil)
    label.configure(image=img_tk)
    label.image = img_tk

# --- Cierre Seguro de la Aplicación ---
# Se asegura de que la cámara se libere correctamente.
def on_closing():
    control_camara(iniciar=False)
    ventana.destroy()

# =================================================================================
# === CONSTRUCCIÓN DE LA INTERFAZ GRÁFICA (GUI) ===
# =================================================================================

# --- Ventana Principal ---
# Creación y configuración de la ventana raíz de la aplicación.
ventana = tk.Tk()
ventana.title("Contabilizador de Manchas en Tiempo Real")
ventana.config(bg=BG_COLOR)
ventana.protocol("WM_DELETE_WINDOW", on_closing)

# --- Visores de Imágenes ---
# Creación de los marcos y etiquetas donde se mostrarán los videos.
frame_imagenes = tk.Frame(ventana, bg=BG_COLOR)
frame_imagenes.pack(pady=10, padx=10, fill='x', expand=True)

lbl_original = tk.Label(bg="black")
lbl_umbralizada = tk.Label(bg="black")
visores = [("1. Imagen Real", lbl_original), ("2. Imagen Umbralizada", lbl_umbralizada)]

for titulo, visor_label in visores:
    frame = tk.Frame(frame_imagenes, bg=FRAME_COLOR, bd=1, relief='sunken')
    frame.pack(side='left', padx=10, fill='x', expand=True)
    tk.Label(frame, text=titulo, font=("Times New Roman", 12, "bold"), bg=FRAME_COLOR, fg=TEXT_COLOR).pack(pady=(5,0))
    visor_label.pack(in_=frame, padx=5, pady=5)

# --- Panel de Controles Inferior ---
# Estructura de tres columnas para organizar los botones, el slider y los créditos.
frame_controles_inferior = tk.Frame(ventana, bg=BG_COLOR)
frame_controles_inferior.pack(pady=10, padx=10, fill='x', expand=True)

# Columna 1: Botones 
col1 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col1.pack(side='left', fill='both', expand=True)
btn_start = tk.Button(col1, text="Detección Automatica", command=lambda: control_camara(True), font=("Times New Roman", 12), width=18, bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_start.pack(pady=5)
btn_stop = tk.Button(col1, text="Detección Detección", command=lambda: control_camara(False), font=("Times New Roman", 12), width=18, state="disabled", bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_stop.pack(pady=5)
btn_load = tk.Button(col1, text="Cargar Imagen", command=cargar_imagen, font=("Times New Roman", 12), width=18, bg=BUTTON_COLOR, fg=TEXT_COLOR, relief='flat', activebackground='#555555', activeforeground=TEXT_COLOR)
btn_load.pack(pady=5)

# Columna 2: Contador y Slider de Ajuste
col2 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col2.pack(side='left', fill='both', expand=True)
lbl_conteo = tk.Label(col2, text="MANCHAS ENCONTRADAS:", font=("Times New Roman", 22, "bold"), fg="#4FC3F7", bg=BG_COLOR)
lbl_conteo.pack(pady=(5, 10))
tk.Label(col2, text="Ajuste de Umbral:", font=("Times New Roman", 12), bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(5,0))
slider_umbral = Scale(col2, from_=0, to=255, orient='horizontal', length=250, bg=BG_COLOR, fg=TEXT_COLOR, troughcolor='#757575', highlightthickness=0, activebackground=BUTTON_COLOR, 
                    command=lambda e: process_frame(source_image) if source_image is not None else None)
slider_umbral.set(127)
slider_umbral.pack(pady=(0, 5))

# Columna 3: Créditos e Información
col3 = tk.Frame(frame_controles_inferior, bg=BG_COLOR)
col3.pack(side='left', fill='both', expand=True)
try:
    logo_pil = Image.open("UBB.png")
    h, w = logo_pil.height, logo_pil.width
    logo_resized = logo_pil.resize((int(60 * (w/h)), 60), Image.Resampling.LANCZOS)
    logo_tk = ImageTk.PhotoImage(logo_resized)
    lbl_logo = tk.Label(col3, image=logo_tk, bg=BG_COLOR)
    lbl_logo.image = logo_tk
    lbl_logo.pack(pady=(1,0)) 
except FileNotFoundError:
    tk.Label(col3, text="Logo 'UBB.png' no encontrado", font=("Times New Roman", 8), bg=BG_COLOR, fg="yellow").pack(pady=5)
tk.Label(col3, text="Desarrollado por Cristóbal Parra A.", font=("Times New Roman", 10), bg=BG_COLOR, fg=TEXT_COLOR).pack()
tk.Label(col3, text="Ingeniería Civil en Automatización", font=("Times New Roman", 9, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack()
tk.Label(col3, text="2025-1", font=("Times New Roman", 9, "italic"), bg=BG_COLOR, fg=TEXT_COLOR).pack()

# --- INICIO DE LA APLICACIÓN ---
ventana.mainloop()