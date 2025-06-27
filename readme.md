# 運用連絡体制ツール
アラートエスカレーション先のリストを保存し、参照するためのツール
## 動作要件
    - python 3.9以降
    - bottle,beaker 使う

## インストール
1. git cloneする
2. ボリューム用ディレクトリを作成する  
   `# mkdir -p ./data`
4. コンテナをビルドする  
   `# podman build --no-cache -t my-bottle-app .`
5. コンテナ起動する  
   `# podman run -d -p 8080:8080 -v ./data:/app/data my-bottle-app`
6. URLアクセスする  
   `http://ホストIP:8080`

## apiの使い方(mattermost)
/api/list
- ユーザーリストを一覧で取得

/api/detail/{id}
- ユーザーIDを入れる事で詳細情報を取得

/api/search?
- ユーザー名の一部を入れる事で詳細情報を取得(複数候補がある場合は最初の1つだけ表示)
