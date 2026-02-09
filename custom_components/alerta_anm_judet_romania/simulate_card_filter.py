import re

def filter_messages(text_complet, numeJudet='Galați'):
    regex = re.compile(r'MESAJ\s+(\d+)([\s\S]*?)(?=(?:MESAJ\s+\d+)|$)', re.IGNORECASE)
    matches = regex.findall(text_complet)
    html_final = ''
    for numar, msg in matches:
        msg_lower = msg.lower()
        countyLower = numeJudet.lower()
        isGeneral = bool(re.search(r'atenționare|atentionare|informare|atenționare generală', msg_lower, re.IGNORECASE))
        mentionsCounty = countyLower in msg_lower
        if not isGeneral and not mentionsCounty:
            continue
        # simple formatting for test
        html_final += f"MESAJ {numar}\n{msg.strip()}\n\n"
    return html_final.strip()

if __name__ == '__main__':
    text = (
        'MESAJ 1\nATENȚIONARE GENERALĂ:\nSe recomandă prudență. Urmăriți sursele oficiale.\n\n'
        'MESAJ 2\nCOD GALBEN:\nIași - Vânt puternic în zona montană.\n'
    )
    print('Input text:\n')
    print(text)
    print('\nFiltered output:\n')
    print(filter_messages(text))
