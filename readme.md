# 運用連絡体制ツール
アラートエスカレーション先のリストを保存し、参照するためのツール
## 動作要件
    - python 3.9以降
    - bottle,beaker 使う

## インストール
1. git cloneする
2. コンテナをビルドする  
   `# podman build --no-cache -t my-bottle-app .`
3. コンテナ起動する  
   `# podman run -d -p 8080:8080 my-bottle-app`
4. URLアクセスする  
   `http://ホストIP:8080`
