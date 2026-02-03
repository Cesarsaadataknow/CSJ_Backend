#!/bin/bash
#Variables
ACR_NAME="registrycsj"
IMAGE_NAME="csj-frontend"
ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
VERSION="v19"
 
# Iniciar sesión en el registro de contenedores de Azure
az acr login --name "$ACR_NAME"
 
# Construir la imagen Docker con tag de versión
docker build -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$VERSION" .
 
# Subir la imagen al ACR
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$VERSION"