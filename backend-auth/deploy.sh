# Variables
ACR_NAME="chatbotgptacr"
IMAGE_NAME="softia-backend"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
VERSION="1.2"
 
# Iniciar sesión en Azure
az acr login --name "$ACR_NAME"
 
# Construir la imagen Docker con dos tags: latest y versión específica
docker build -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$VERSION" .
 
# Enviar ambas etiquetas (tags) al ACR
# docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$VERSION"
 