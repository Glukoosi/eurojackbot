mkdir deploy_package
cp -r main.py lib/ deploy_package/
pip3 install --target ./deploy_package -r requirements.txt
cd deploy_package
zip -r ../deployment-package.zip .
cd ..
rm -rf deploy_package
aws lambda update-function-code \
    --function-name eurojackbot \
    --zip-file fileb://deployment-package.zip
sleep 1
aws lambda update-function-configuration \
    --function-name eurojackbot \
    --environment file://env_prod.json
rm deployment-package.zip