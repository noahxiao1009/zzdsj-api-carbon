@echo off

set registry="--registry=https://artsh.zte.com.cn/artifactory/api/npm/rnia-npm-virtual/"
set scriptDir=%~dp0
cd ..
del /f package-lock.json
rmdir /s /q .angular

echo ��ʼ��װ�ֿ�����...
cmd /c npm install --unsafe-perm --force --ignore-scripts %registry%
if %errorlevel% NEQ 0 (
    echo "==> ����: �޷���װ�ֿ�����..."
    exit /b 1
)

echo ��ʼ����icon-font...
cmd /c npm update --force --ignore-scripts %registry% @rdkmaster/icon-font
if %errorlevel% NEQ 0 (
    echo "==> ����: ͼ������ʧ��..."
    exit /b 1
)


echo ��ʼ����lui-sdk...
cmd /c npm update --force --ignore-scripts %registry% @rdkmaster/lui-sdk @rdkmaster/lui-sdk-mobile
if %errorlevel% NEQ 0 (
    echo "==> ����: lui-sdk����ʧ��..."
    exit /b 1
)

echo ��ʼ��װjigsaw��formly...
cmd /c npm install @rdkmaster/jigsaw@governance18 @rdkmaster/formly@governance18 --force --ignore-scripts %registry%
if %errorlevel% NEQ 0 (
    echo "==> ����: ����jigsaw��governance18�汾ʧ��..."
    exit /b 1
)

if not "%1" == "silent" pause


