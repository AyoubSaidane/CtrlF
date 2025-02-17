import json
import re
from typing import Dict, List, Optional

def extract_last_response(input_text: str) -> str:
    """Extrait le texte de la dernière balise <response> dans l'input."""
    responses = re.findall(r'<response>(.*?)</response>', input_text, re.DOTALL)
    return responses[-1].strip() if responses else ""

def clean_string(s: str) -> str:
    """Nettoie une chaîne de caractères pour la rendre compatible JSON."""
    # Remplace les guillemets simples par des guillemets doubles
    s = s.replace("'", '"')
    
    try:
        # Trouve le premier crochet ouvrant et le dernier crochet fermant
        start = s.find('[')
        end = s.rfind(']')
        
        if start != -1 and end != -1:
            # Extrait le contenu entre les crochets
            content = s[start:end+1]
            
            # Nettoie le contenu en ne gardant que les objets avec les champs requis
            matches = re.finditer(r'{[^}]*"file_name"[^}]*"url"[^}]*"page"[^}]*}|{[^}]*"page"[^}]*"url"[^}]*"file_name"[^}]*}|{[^}]*"url"[^}]*"page"[^}]*"file_name"[^}]*}', content)
            
            cleaned_objects = []
            for match in matches:
                obj_str = match.group()
                try:
                    # Nettoie l'objet
                    obj_str = re.sub(r',\s*"content":[^}]*', '', obj_str)  # Supprime le champ content
                    obj = json.loads(obj_str)
                    if all(key in obj for key in ['file_name', 'url', 'page']):
                        cleaned_obj = {
                            'file_name': obj['file_name'],
                            'url': obj['url'],
                            'page': obj['page']
                        }
                        cleaned_objects.append(cleaned_obj)
                except:
                    continue
            
            return json.dumps(cleaned_objects)
            
    except Exception as e:
        print(f"Erreur dans clean_string: {e}")
    
    return "[]"

def extract_last_source(input_text: str) -> List[Dict[str, str]]:
    """Extrait les informations de la dernière balise <source> dans l'input."""
    sources = re.findall(r'<source>(.*?)</source>', input_text, re.DOTALL)
    if not sources:
        print("No sources found in input")
        return []
    
    try:
        # Nettoie et formate la chaîne pour la rendre compatible JSON
        last_source = sources[-1].strip()
        print("Original source length:", len(last_source))
        
        last_source = clean_string(last_source)
        print("Cleaned source length:", len(last_source))
        
        # Si la chaîne est vide ou contient juste [], retourne une liste vide
        if last_source == '[]' or not last_source:
            print("Empty source found")
            return []
            
        parsed_sources = json.loads(last_source)
        print("Successfully parsed JSON, type:", type(parsed_sources))
        
        # Traite tous les éléments de la liste
        if isinstance(parsed_sources, list):
            cleaned_sources = []
            for source in parsed_sources:
                if isinstance(source, dict) and all(key in source for key in ['file_name', 'url', 'page']):
                    cleaned_source = {
                        'file_name': source.get('file_name', ''),
                        'url': source.get('url', ''),
                        'page': source.get('page', 0)
                    }
                    cleaned_sources.append(cleaned_source)
            print(f"Found {len(cleaned_sources)} valid sources")
            return cleaned_sources
        return []
    except json.JSONDecodeError as e:
        print(f"Erreur de parsing JSON: {e}")
        print(f"Position de l'erreur: caractère {e.pos}")
        print(f"Ligne de l'erreur: {e.lineno}, colonne: {e.colno}")
        print(f"Document jusqu'à l'erreur: {last_source[max(0, e.pos-50):e.pos]}<<<ERREUR ICI>>>{last_source[e.pos:e.pos+50]}")
        return []
    except Exception as e:
        print(f"Erreur inattendue: {e}")
        return []

def format_documents(sources: List[Dict[str, any]]) -> List[Dict]:
    """Formate les sources en documents selon le format de sortie requis."""
    documents = []
    for source in sources:
        print("Processing source:", source)  # Debug log
        if all(key in source for key in ['file_name', 'url', 'page']):
            doc = {
                "title": source['file_name'],
                "url": source['url'],
                "page": source['page']
            }
            print("Adding document:", doc)  # Debug log
            documents.append(doc)
    return documents

def convert_format(input_text: str) -> Dict:
    """Convertit l'input au format de sortie requis."""
    # Extraction des données
    text = extract_last_response(input_text)
    sources = extract_last_source(input_text)
    
    # Construction de la sortie
    output = {
        "text": text,
        "images": [],  # Liste vide comme demandé
        "experts": [], # Liste vide comme demandé
        "documents": format_documents(sources)
    }
    
    return output

def process_input(input_text: str) -> str:
    """Traite l'input et retourne la sortie formatée en JSON."""
    result = convert_format(input_text)
    return json.dumps(result, indent=4)

if __name__ == "__main__":
    # Example input for testing
    TEST_INPUT = """
    The media and entertainment industry is a significant contributor to New York City's economy, providing high-quality jobs, especially in an era where low-paying service jobs are prevalent. Over the past decade, the industry has experienced substantial change and growth in New York City, even amidst national and regional economic challenges. From 2012 to 2014, the industry saw steady growth, particularly in scripted TV series, which offer stable, long-term employment.\n\nThe Mayor's Office of Media and Entertainment (MOME), including its Office of Film, Theatre and Broadcasting (MOFTB), has been supporting New York City's media and entertainment sector since 1966. MOME issues permits, coordinates services, and manages the \"Made in NY\" logo and marketing campaign for eligible productions. The City is committed to the media industry and is developing initiatives to leverage its digital capabilities, such as the new Engineering and Applied Science Campus and the establishment of a dedicated NYC Digital Office.\n\nRAG Response: Réponse à votre question : Réponse à votre question : media market in New York\n\n<response>\nThe media and entertainment industry significantly contributes to New York City's economy by providing high-quality jobs. Over the past decade, the industry has experienced considerable change and growth in New York City, even amidst national and regional economic challenges. From 2012 to 2014, the industry in New York City saw steady growth, especially in areas like scripted TV series, which offer stable, long-term employment. The Mayor's Office of Media and Entertainment (MOME), including its Office of Film, Theatre and Broadcasting (MOFTB), has been supporting New York City's media and entertainment sector since 1966. MOME issues permits, coordinates services, and manages the \"Made in NY\" logo and marketing campaign for eligible productions. The City is dedicated to the media industry and is developing initiatives to leverage the City's digital capabilities, such as the new Engineering and Applied Science Campus and the establishment of a dedicated NYC Digital Office.\n\n</response>\n\n<source>\n[{'file_name': 'e23ef9fa-9ef8-4a2a-8c94-20042d623333.pdf', 'url': 'https://jziorpwgdnhsijnqsott.supabase.co/storage/v1/object/public/slides/e23ef9fa-9ef8-4a2a-8c94-20042d623333.pdf?', 'page': 2, 'content': \"START OF PAGE: 2\\n# Introduction\\n\\nThe media and entertainment industry is an important contributor to New York City's economy, providing high quality jobs in an era when low-paying service jobs have become the norm. Over the past ten years, this industry's presence in New York City has seen significant change and growth, even in the face of the national and regional economic downturn.\\n\\nThis reports aims to analyze the development and growth of NYC media by examining different subsectors and identifying the main trends that have shaped and will continue to shape NYC's media and digital media sectors.\\n\\nNew York City has long sought to facilitate media production in the City. Since its establishment in 1966, the Mayor's Office of Media and Entertainment (MOME), through its Office of Film, Theatre and Broadcasting (MOFTB) has served New York City's media and entertainment industry issuing permits, coordinating services and developing the Made in NY logo and marketing campaign for qualifying productions. With changing technology and new challenges, City maintains its commitment to the media industry, developing a number of initiatives to build on the City's digital potential, most notably including the new Engineering and Applied Science Campus and the creation of a dedicated NYC Digital Office.\\nEND OF PAGE: 2\"}, {'file_name': '0eb4493b-774d-420b-a1af-be20e284e8db.pdf', 'url': 'https://jziorpwgdnhsijnqsott.supabase.co/storage/v1/object/public/slides/0eb4493b-774d-420b-a1af-be20e284e8db.pdf?', 'page': 2, 'content': 'START OF PAGE: 2\\n# Introduction\\n\\nThe media and entertainment industry is an important contributor to New York City\\'s economy, providing high quality jobs which out-performed the US economy through the financial downturn.\\n\\nSince our last report in 2012 the industry in New York City has seen a period of steady growth, particularly in sub sectors like scripted TV series which offer long-term and predictable employment.\\n\\nThis report, completed in April 2015, serves as an update to our 2012 publication. The report analyzes the development and growth of NYC media in the period 2012 through 2014, by once again examining different subsectors and identifying the latest trends that have shaped and will continue to shape NYC\\'s media and digital media sectors.\\n\\nSince its establishment in 1966, the Mayor\\'s Office of Media and Entertainment (MOME), through its Office of Film, Theatre and Broadcasting (MOFTB) has served New York City\\'s media and entertainment industry - issuing permits, coordinating services and deploying the \"Made in NY\" logo and marketing campaign for qualifying productions. Under the new mayoral administration, MOME maintains its strong commitment to fostering the Media and Entertainment industry, ensuring its services evolve to address the latest needs of companies and workers living, working and operating within the city.\\nEND OF PAGE: 2'}]\n</source>\n\n\n\n<response>\nThe media and entertainment industry significantly contributes to New York City's economy by providing high-quality jobs. Over the past decade, the industry has experienced considerable change and growth in New York City, even amidst national and regional economic challenges. From 2012 to 2014, the industry in New York City saw steady growth, especially in areas like scripted TV series, which offer stable, long-term employment. The Mayor's Office of Media and Entertainment (MOME), including its Office of Film, Theatre and Broadcasting (MOFTB), has been supporting New York City's media and entertainment sector since 1966. MOME issues permits, coordinates services, and manages the \"Made in NY\" logo and marketing campaign for eligible productions. The City is dedicated to the media industry and is developing initiatives to leverage the City's digital capabilities, such as the new Engineering and Applied Science Campus and the establishment of a dedicated NYC Digital Office.\n\n</response>\n\n<source>\n[{'file_name': '0eb4493b-774d-420b-a1af-be20e284e8db.pdf', 'url': 'https://jziorpwgdnhsijnqsott.supabase.co/storage/v1/object/public/slides/0eb4493b-774d-420b-a1af-be20e284e8db.pdf?', 'page': 2, 'content': 'START OF PAGE: 2\\n# Introduction\\n\\nThe media and entertainment industry is an important contributor to New York City\\'s economy, providing high quality jobs which out-performed the US economy through the financial downturn.\\n\\nSince our last report in 2012 the industry in New York City has seen a period of steady growth, particularly in sub sectors like scripted TV series which offer long-term and predictable employment.\\n\\nThis report, completed in April 2015, serves as an update to our 2012 publication. The report analyzes the development and growth of NYC media in the period 2012 through 2014, by once again examining different subsectors and identifying the latest trends that have shaped and will continue to shape NYC\\'s media and digital media sectors.\\n\\nSince its establishment in 1966, the Mayor\\'s Office of Media and Entertainment (MOME), through its Office of Film, Theatre and Broadcasting (MOFTB) has served New York City\\'s media and entertainment industry - issuing permits, coordinating services and deploying the \"Made in NY\" logo and marketing campaign for qualifying productions. Under the new mayoral administration, MOME maintains its strong commitment to fostering the Media and Entertainment industry, ensuring its services evolve to address the latest needs of companies and workers living, working and operating within the city.\\nEND OF PAGE: 2'}, {'file_name': 'e23ef9fa-9ef8-4a2a-8c94-20042d623333.pdf', 'url': 'https://jziorpwgdnhsijnqsott.supabase.co/storage/v1/object/public/slides/e23ef9fa-9ef8-4a2a-8c94-20042d623333.pdf?', 'page': 2, 'content': \"START OF PAGE: 2\\n# Introduction\\n\\nThe media and entertainment industry is an important contributor to New York City's economy, providing high quality jobs in an era when low-paying service jobs have become the norm. Over the past ten years, this industry's presence in New York City has seen significant change and growth, even in the face of the national and regional economic downturn.\\n\\nThis reports aims to analyze the development and growth of NYC media by examining different subsectors and identifying the main trends that have shaped and will continue to shape NYC's media and digital media sectors.\\n\\nNew York City has long sought to facilitate media production in the City. Since its establishment in 1966, the Mayor's Office of Media and Entertainment (MOME), through its Office of Film, Theatre and Broadcasting (MOFTB) has served New York City's media and entertainment industry issuing permits, coordinating services and developing the Made in NY logo and marketing campaign for qualifying productions. With changing technology and new challenges, City maintains its commitment to the media industry, developing a number of initiatives to build on the City's digital potential, most notably including the new Engineering and Applied Science Campus and the creation of a dedicated NYC Digital Office.\\nEND OF PAGE: 2\"}]\n</source>\n\n
    """
    
    try:
        output = process_input(TEST_INPUT)
        print("Test output:", output)
    except Exception as e:
        print(f"Error during test: {e}")