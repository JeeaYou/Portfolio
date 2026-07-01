from PIL import Image
import torch
import torch.nn as nn
from torchvision import models, transforms
import matplotlib.pyplot as plt
plt.rc('font', family='NanumGothic')  # For Windows
import warnings
warnings.filterwarnings('ignore')
import os
from common.services import get_lang

lang = get_lang()

def image_test(image):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")  # device 객체

    transforms_test = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    model = models.resnet34(pretrained=True)
    num_features = model.fc.in_features
    model.fc = nn.Linear(num_features, 3)
    base_dir = os.path.dirname(__file__)  # service_cataract.py 있는 폴더
    model_path = os.path.join(base_dir, "resnet34.pth")
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))    
    model.eval()

    model = model.to(device)
    image = Image.open(image).convert('RGB')
    image = transforms_test(image).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(image)
        num_zero = list(outputs[0])[0]
        num_first = list(outputs[0])[1]
        
        score = int(torch.max(outputs) / (num_zero + num_first) * 100)
        
        if score > 100:
            score = 100
        if torch.max(outputs) == list(outputs[0])[0]:
            class_name = '백내장' if lang == 'ko' else 'Cataract'

        elif torch.max(outputs) == list(outputs[0])[1]:
            class_name = '정상' if lang == 'ko' else 'Normal'

        return class_name, score

