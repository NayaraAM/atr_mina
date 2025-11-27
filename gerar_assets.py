import pygame
import os

# Inicializa PyGame
pygame.init()

# Configurações
WIDTH, HEIGHT = 1000, 1000
COR_TERRA = (160, 120, 80)     # Marrom
COR_PISTA = (100, 100, 100)    # Cinza
COR_ZONA_A = (100, 100, 200)   # Azulado (Garagem)
COR_ZONA_B = (200, 100, 100)   # Avermelhado (Lavra)
COR_ZONA_C = (100, 200, 100)   # Esverdeado (Britador)
LARGURA_PISTA = 80

# Garante que a pasta existe
if not os.path.exists("interface/assets"):
    try:
        os.makedirs("interface/assets")
    except:
        pass # Se já existir ou falhar, tenta seguir

# --- GERAR MAPA DE FUNDO ---
surf = pygame.Surface((WIDTH, HEIGHT))
surf.fill(COR_TERRA)

# Desenha o retângulo da estrada (Baseado na rota padrão)
pontos = [(100, 100), (800, 100), (800, 800), (100, 800)]
pygame.draw.lines(surf, COR_PISTA, True, pontos, LARGURA_PISTA)

# Zonas
pygame.draw.rect(surf, COR_ZONA_A, (50, 50, 100, 100))   # Garagem
pygame.draw.rect(surf, COR_ZONA_B, (750, 50, 100, 100))  # Lavra
pygame.draw.rect(surf, COR_ZONA_C, (750, 750, 100, 100)) # Britador

# Salvar
caminho = "interface/assets/mapa_fundo.png"
try:
    pygame.image.save(surf, caminho)
    print(f"[OK] Mapa gerado em: {caminho}")
except Exception as e:
    print(f"[ERRO] Não foi possível salvar em interface/assets. Tente criar a pasta manualmente. {e}")

# --- GERAR SPRITE DUMMY (Apenas para garantir que o arquivo exista) ---
surf_truck = pygame.Surface((32, 32))
surf_truck.fill((255, 255, 0))
try:
    pygame.image.save(surf_truck, "interface/assets/caminhao_topdown.png")
except:
    pass