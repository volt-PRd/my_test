from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import base64
import time

app = Flask(__name__)

def get_witanime_links(episode_url):
    """
    الدالة الرئيسية التي تستخدم Playwright لتجاوز الحماية المتقدمة.
    """
    with sync_playwright() as p:
        browser = None  # تهيئة المتغير خارج كتلة try
        try:
            # إطلاق متصفح Chromium في الخلفية
            # نضيف بعض الوسائط لتجنب المشاكل في بيئة الخادم
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]) 
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            print(f"Navigating to episode page with Playwright: {episode_url}")
            # الذهاب إلى الصفحة والانتظار حتى يتم تحميلها بالكامل
            page.goto(episode_url, timeout=90000, wait_until='domcontentloaded')
            
            # الانتظار لظهور عنصر قائمة السيرفرات، وهو دليل على أن الصفحة الحقيقية قد تم تحميلها
            print("Waiting for server list to appear...")
            page.wait_for_selector('ul.servers-list li[data-player-id]', timeout=45000)
            
            print("Page loaded successfully. Scraping content...")
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            post_id_tag = soup.find('div', {'class': 'Live-Player'})
            if not post_id_tag or not post_id_tag.has_attr('data-post-id'):
                raise ValueError("Could not find post_id. The page structure might have changed or protection is active.")
            post_id = post_id_tag['data-post-id']
            print(f"Found Post ID: {post_id}")

            server_tags = soup.select('ul.servers-list li')
            all_servers_links = []

            for server_tag in server_tags:
                player_id = server_tag.get('data-player-id')
                if not player_id: continue

                server_name = server_tag.text.strip()
                print(f"\nProcessing Server: {server_name} (Player ID: {player_id})")

                # لا نحتاج لعمل طلب AJAX منفصل، بل ننقر على العنصر مباشرة في المتصفح الآلي
                try:
                    # النقر على زر السيرفر لتحميل الـ iframe
                    page.click(f'li[data-player-id="{player_id}"]', timeout=10000)
                    # الانتظار قليلاً ليتم تحميل الـ iframe
                    time.sleep(3) 
                    
                    # العثور على الـ iframe الخاص بالمشغل
                    iframe = page.frame_locator('#iframe-container iframe').first
                    iframe_url = iframe.evaluate('() => window.location.href')
                    print(f"Found iframe URL: {iframe_url}")

                    if "dood" in iframe_url or "yonaplay" in iframe_url:
                         all_servers_links.append({"name": server_name, "quality": "Direct", "url": iframe_url})
                         print(f"Added direct link for server '{server_name}'.")
                         continue

                    # جلب محتوى الـ iframe
                    iframe_content = iframe.content()
                    
                    encrypted_match = re.search(r'sources:\s*JSON\.parse\(atob\("([^"]+)"\)\)', iframe_content)
                    if not encrypted_match:
                        print(f"Skipping server '{server_name}': Could not find encrypted sources in iframe.")
                        continue

                    encrypted_data = encrypted_match.group(1)
                    decoded_data = base64.b64decode(encrypted_data).decode('utf-8')
                    video_matches = re.findall(r'{"file":"([^"]+)","label":"([^"]+)"}', decoded_data)

                    if not video_matches:
                        print(f"Skipping server '{server_name}': Could not parse video links.")
                        continue
                    
                    print(f"Successfully extracted {len(video_matches)} qualities for server '{server_name}'.")
                    for video_url, quality in video_matches:
                        all_servers_links.append({
                            "name": f"{server_name} - {quality}",
                            "quality": quality,
                            "url": video_url.replace('\\', '')
                        })

                except Exception as e:
                    print(f"Could not process server '{server_name}'. Error: {e}")

            browser.close()
            return all_servers_links

        except Exception as e:
            print(f"A critical error occurred in Playwright process: {e}")
            if browser and browser.is_connected():
                browser.close()
            return None

@app.route('/scrape', methods=['POST'])
def handle_scrape_request():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"success": False, "error": "Missing 'url' in request body"}), 400
    
    episode_url = data['url']
    if 'witanime.red' not in episode_url:
        return jsonify({"success": False, "error": "This API is specifically for witanime.red URLs."}), 400

    scraped_links = get_witanime_links(episode_url)
    
    if scraped_links:
        return jsonify({"success": True, "servers": scraped_links}), 200
    else:
        return jsonify({"success": False, "error": "Failed to scrape links using Playwright. The site's protection may be too strong or the structure has changed."}), 500

# إضافة نقطة نهاية بسيطة للتأكد من أن الـ API يعمل
@app.route('/')
def index():
    return "<h1>Anime Scraper API is running!</h1><p>Use the /scrape endpoint with a POST request to fetch links.</p>"

if __name__ == '__main__':
    # Render يستخدم gunicorn، لذا هذا الجزء للتشغيل المحلي فقط
    app.run(host='0.0.0.0', port=5000, debug=True)
