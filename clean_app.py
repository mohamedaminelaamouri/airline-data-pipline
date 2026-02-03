import re

with open('realtime_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Nettoyer les espaces apres guillemets au debut des strings
content = re.sub(r'" ([A-Z])', r'"\1', content)

# Corriger les status labels avec espaces
content = content.replace('" En ligne"', '"En ligne"')
content = content.replace('" Attention"', '"Attention"')
content = content.replace('" Hors ligne"', '"Hors ligne"')

# Nettoyer les accents problematiques
content = content.replace('é', 'e')
content = content.replace('è', 'e')
content = content.replace('ê', 'e')
content = content.replace('à', 'a')
content = content.replace('â', 'a')
content = content.replace('ù', 'u')
content = content.replace('û', 'u')
content = content.replace('ô', 'o')
content = content.replace('î', 'i')
content = content.replace('ï', 'i')
content = content.replace('ç', 'c')

with open('realtime_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Nettoyage termine!')
