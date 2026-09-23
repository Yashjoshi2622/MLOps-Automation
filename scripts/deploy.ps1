docker stop mlops-app 2>$null
docker rm mlops-app 2>$null

docker build -t mlops-app .

docker run -d -p 8000:8000 --name mlops-app mlops-app