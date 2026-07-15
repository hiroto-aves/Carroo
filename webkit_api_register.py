import requests
import xml.etree.ElementTree as ET
import re

# ----------------------------------------------------
# ユーザー提供情報
# ----------------------------------------------------
API_ENDPOINT = "https://www.wkit.jp/api/LoadInfo"
API_KEY = "RhpQw9t77MGNLQNOa28A"
PERSON_ID = "27113000530001"

# ----------------------------------------------------
# 荷物登録用 XML リクエストボディ
# ----------------------------------------------------
# 注意: 登録する荷物の情報に合わせて、<load_data>内のデータを適切に修正してください。
# 特に日付(loaddate, destdate)は未来の日付に変更しないとエラーになる場合があります。
REQUEST_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<webkit>
    <apikey>{api_key}</apikey>
    <personid>{person_id}</personid>
    <load_data> 
        <operation>I</operation>
        <memberid>271130005300</memberid>
        
        <loaddate>2025-11-15 10:00</loaddate>
        <loaddatetype>1</loaddatetype>
        <loadprefecture>17</loadprefecture>
        <loadarea>千代田区</loadarea> 
        <loadaddress>丸の内</loadaddress>
        <destdate>2025-11-16 15:00</destdate>
        <destdatetype>1</destdatetype>
        <destprefecture>30</destprefecture>
        <destarea>大阪市中央区</destarea> 
        <destaddress>船場</destaddress>
        
        <loadkind>21</loadkind>
        <loadkind_other>APIテスト用荷物-最終決定版</loadkind_other>
        <packagetype>7</packagetype>
        <packagetype_other></packagetype_other>
        <transporttype>3</transporttype>
        <weight>5.0</weight>
        
        <carkindtype>5</carkindtype> 
        <carkind>1</carkind>
        <trayheighttype></trayheighttype>
        <traywidthtype></traywidthtype>
        <traylengthtype></traylengthtype>
        <loadunit></loadunit>
        <suspension></suspension>
        <traylength></traylength>
        <traylength_op></traylength_op>
        <trayheight></trayheight>
        <trayheight_op></trayheight_op>
        <traywidth></traywidth>
        <traywidth_op></traywidth_op>
        <aori>1</aori>
        <handling>1</handling>
        <mix>1</mix>
        <equipment>台車</equipment>
        <note1></note1>
        <safetyunit>1</safetyunit>
        <safetyunit_other></safetyunit_other>
        <owntruck>1</owntruck>
        <opentype>1</opentype>
        <opentype_id></opentype_id>
        
        <personname>API登録者</personname>
        <tel></tel>
        <portablephone>090-1234-5678</portablephone>
        <personname_kana></personname_kana>
        <fax></fax>
        
        <charge>15000</charge>
        <charge_taxtype>1</charge_taxtype>
        <charge_nego>2</charge_nego> 
        <toll_flg>0</toll_flg>
        
        <toll></toll>
        <expense></expense>
        <incidental_fee></incidental_fee>
        <vehicle_pracement_fee></vehicle_pracement_fee>
        <loading_fee></loading_fee>
        <inventory_fee></inventory_fee>
        <incidental_contents></incidental_contents>
        
        <insurance_extra>0</insurance_extra> 
        <contracttype>3</contracttype> 
        <reg_number>1</reg_number>
        <memo></memo>
    </load_data>    
</webkit>
"""

# ----------------------------------------------------
# 関数定義
# ----------------------------------------------------
def register_webkit_loadinfo():
    """
    WebKITの荷物登録APIを呼び出し、レスポンスを出力する。
    """
    print(f"** WebKIT 荷物登録 APIテスト開始 **")
    print(f"エンドポイント: {API_ENDPOINT}")
    
    # テンプレートに実際のAPIキーと担当者IDを挿入
    request_xml = REQUEST_XML_TEMPLATE.format(
        api_key=API_KEY,
        person_id=PERSON_ID
    ).strip()
    
    HEADERS = {
        "Content-Type": "application/xml; charset=UTF-8",
    }

    print("-" * 40)
    print("▼ 送信 XML リクエスト ▼")
    print(request_xml)
    print("-" * 40)

    try:
        response = requests.post(
            API_ENDPOINT, 
            headers=HEADERS, 
            data=request_xml.encode('utf-8'),
            timeout=30
        )
        
        response_charset = 'utf-8'
        response_text = response.content.decode(response_charset, errors='ignore')

        print(f"HTTPステータスコード: {response.status_code}")
        print("-" * 40)
        print("▼ レスポンス XML ▼")
        
        # 成功/失敗に関わらずレスポンスXMLを表示し、ステータスをチェック
        try:
            root = ET.fromstring(response_text)
            status_tag = root.find('.//status')
            
            if status_tag is not None and status_tag.text == '0':
                new_slipno = root.find('.//slipno')
                print("✅ 成功: 荷物登録が正常に完了しました。")
                if new_slipno is not None:
                    print(f"   登録された伝票番号: {new_slipno.text}")
            elif status_tag is not None and status_tag.text != '0':
                print(f"❌ 警告/エラー: ステータスコードが 0 以外です (コード: {status_tag.text})")
            elif response.status_code != 200:
                print(f"❌ エラー: HTTPステータスコードが 200 ではありません。")
            else:
                print("✅ 成功 (伝票番号タグなし): 処理は成功したようですが、伝票番号タグが見つかりませんでした。")
                
            # XMLを整形して表示 (可読性のため)
            print(ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8', errors='ignore'))
            
        except ET.ParseError:
            print("※ XML解析エラー: レスポンスが不正なXML形式の可能性があります。")
            print(response_text)
        
    except requests.exceptions.RequestException as e:
        print(f"🚨 リクエスト中に例外が発生しました: ネットワークエラーまたはタイムアウト ({e})")

# ----------------------------------------------------
# メイン処理
# ----------------------------------------------------
if __name__ == "__main__":
    # 修正前: test_webkit_loadinfo_api_with_xml_parse() 
    # 修正後: register_webkit_loadinfo()
    register_webkit_loadinfo()