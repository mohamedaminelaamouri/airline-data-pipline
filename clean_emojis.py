"""
Script pour nettoyer les emojis et accents de realtime_app.py
sans casser l'indentation
"""
import re

# Lire le fichier
with open('realtime_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Pattern pour les emojis (large couverture)
emoji_pattern = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & maps
    "\U0001F700-\U0001F77F"  # alchemical
    "\U0001F780-\U0001F7FF"  # Geometric
    "\U0001F800-\U0001F8FF"  # arrows
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA00-\U0001FA6F"  # chess
    "\U0001FA70-\U0001FAFF"  # symbols
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "]+", 
    flags=re.UNICODE
)

# Remplacements d'accents
accent_map = {
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'à': 'a', 'â': 'a', 'ä': 'a',
    'ù': 'u', 'û': 'u', 'ü': 'u',
    'ô': 'o', 'ö': 'o',
    'î': 'i', 'ï': 'i',
    'ç': 'c',
    'É': 'E', 'È': 'E', 'Ê': 'E',
    'À': 'A', 'Â': 'A',
    'Ù': 'U', 'Û': 'U',
    'Ô': 'O',
    'Î': 'I',
    'Ç': 'C',
    '•': '-',
    '➜': '->',
    '═': '=',
}

cleaned_lines = []
for line in lines:
    # Supprimer les emojis
    new_line = emoji_pattern.sub('', line)
    
    # Remplacer les accents
    for old, new in accent_map.items():
        new_line = new_line.replace(old, new)
    
    # Nettoyer les espaces multiples (mais garder l'indentation)
    # On garde l'indentation en début de ligne
    indent = len(new_line) - len(new_line.lstrip())
    content = new_line[indent:]
    content = re.sub(r'  +', ' ', content)  # double espaces -> simple
    content = content.replace('" ', '"').replace(' "', '"')  # espaces autour guillemets
    
    # Ne pas toucher aux strings avec espaces volontaires
    new_line = new_line[:indent] + content
    
    cleaned_lines.append(new_line)

# Ecrire le fichier
with open('realtime_app.py', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print("Nettoyage termine! Emojis et accents supprimes.")
