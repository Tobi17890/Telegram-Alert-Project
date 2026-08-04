"""Telegram routing configuration by product and province."""

CHAT_ID = -1004389670593
CHAT_ID_OBJECT = {
    "region_1": -1004389670593,
    "region_2": -1003731178845,
    "region_3": -1004300457270,
    "region_4": -1004432057435,
    "region_5": -1004467897003,
    "region_6": -1004324233290
}
TELEGRAM_ROUTES = {

    "TPP": {

        "Phnom Penh": {
            "region": "R1",
            "chat_id": CHAT_ID_OBJECT["region_1"],
            "message_thread_id": 9,
        },

        "Kandal": {
            "region": "R1",
            "chat_id": CHAT_ID_OBJECT["region_1"],
            "message_thread_id": 5,
        },
        
        "Kampot": {
            "region": "R2",
            "chat_id": CHAT_ID_OBJECT["region_2"],
            "message_thread_id": 16,
        },
        
        "KEP": {
            "region": "R2",
            "chat_id": CHAT_ID_OBJECT["region_2"],
            "message_thread_id": 20,
        },
        
        "Takeo": {
            "region": "R2",
            "chat_id": CHAT_ID_OBJECT["region_2"],
            "message_thread_id": 12,
        },
        
        "Prey Veng": {
            "region": "R2",
            "chat_id": CHAT_ID_OBJECT["region_2"],
            "message_thread_id": 8,  
        },
        
        "Svay Rieng": {
            "region": "R2",
            "chat_id": CHAT_ID_OBJECT["region_2"],
            "message_thread_id": 4,
        },
        
        "Sihanouk Ville": {
            "region": "R3",
            "chat_id": CHAT_ID_OBJECT["region_3"],
            "message_thread_id": 16,
        },
        
        "Kampong Chhnang": {
            "region": "R3",
            "chat_id": CHAT_ID_OBJECT["region_3"],
            "message_thread_id": 14,
        },
        
        "Koh Kong": {
            "region": "R3",
            "chat_id": CHAT_ID_OBJECT["region_3"],
            "message_thread_id": 12,
        },
        
        "Kampong Speu": {
            "region": "R3",
            "chat_id": CHAT_ID_OBJECT["region_3"],
            "message_thread_id": 10,
        },
        
        "Pailin": {
            "region": "R4",
            "chat_id": CHAT_ID_OBJECT["region_4"],
            "message_thread_id": 14,
        },
        
        "Banteay Meanchey": {
            "region": "R4",
            "chat_id": CHAT_ID_OBJECT["region_4"],
            "message_thread_id": 12,
        },
        
        "Battambang": {
            "region": "R4",
            "chat_id": CHAT_ID_OBJECT["region_4"],
            "message_thread_id": 8,
        },
        
        "Pursat": {
            "region": "R4",
            "chat_id": CHAT_ID_OBJECT["region_4"],
            "message_thread_id": 4,
        },
        
        "Kampong Thom": {
            "region": "R5",
            "chat_id": CHAT_ID_OBJECT["region_5"],
            "message_thread_id": 8,
        },
        
        "Siem Reap": {
            "region": "R5",
            "chat_id": CHAT_ID_OBJECT["region_5"],
            "message_thread_id": 4,
        },
        
        "Oddar Meanchey": {
            "region": "R5",
            "chat_id": CHAT_ID_OBJECT["region_5"],
            "message_thread_id": 10,
        },
        
        "Preah Vihear": {
            "region": "R5",
            "chat_id": CHAT_ID_OBJECT["region_5"],
            "message_thread_id": 14,
        },
        
        "Mondol Kiri": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 24,
        },
        
        "Ratanak Kiri": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 22,
        },
        
        "Strung Treng": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 20,
        },
        
        "Kratie": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 18,
        },
        
        "Tbong Khmoum": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 16,
        },
        
        "Kampong Cham": {
            "region": "R6",
            "chat_id": CHAT_ID_OBJECT["region_6"],
            "message_thread_id": 14,
        },    
    },

    "CRT": {

        "Phnom Penh": {
                "region": "R1",
                "chat_id": CHAT_ID_OBJECT["region_1"],
                "message_thread_id": 12,
            },

            "Kandal": {
                "region": "R1",
                "chat_id": CHAT_ID_OBJECT["region_1"],
                "message_thread_id": 3,
            },
            
            "Kampot": {
                "region": "R2",
                "chat_id": CHAT_ID_OBJECT["region_2"],
                "message_thread_id": 14,
            },
            
            "KEP": {
                "region": "R2",
                "chat_id": CHAT_ID_OBJECT["region_2"],
                "message_thread_id": 18,
            },
            
            "Takeo": {
                "region": "R2",
                "chat_id": CHAT_ID_OBJECT["region_2"],
                "message_thread_id": 10,
            },
            
            "Prey Veng": {
                "region": "R2",
                "chat_id": CHAT_ID_OBJECT["region_2"],
                "message_thread_id": 6,  
            },
            
            "Svay Rieng": {
                "region": "R2",
                "chat_id": CHAT_ID_OBJECT["region_2"],
                "message_thread_id": 2,
            },
            
            "Sihanouk Ville": {
                "region": "R3",
                "chat_id": CHAT_ID_OBJECT["region_3"],
                "message_thread_id": 8,
            },
            
            "Kampong Chhnang": {
                "region": "R3",
                "chat_id": CHAT_ID_OBJECT["region_3"],
                "message_thread_id": 4,
            },
            
            "Koh Kong": {
                "region": "R3",
                "chat_id": CHAT_ID_OBJECT["region_3"],
                "message_thread_id": 6,
            },
            
            "Kampong Speu": {
                "region": "R3",
                "chat_id": CHAT_ID_OBJECT["region_3"],
                "message_thread_id": 2,
            },
            
            "Pailin": {
                "region": "R4",
                "chat_id": CHAT_ID_OBJECT["region_4"],
                "message_thread_id": 16,
            },
            
            "Banteay Meanchey": {
                "region": "R4",
                "chat_id": CHAT_ID_OBJECT["region_4"],
                "message_thread_id": 10,
            },
            
            "Battambang": {
                "region": "R4",
                "chat_id": CHAT_ID_OBJECT["region_4"],
                "message_thread_id": 6,
            },
            
            "Pursat": {
                "region": "R4",
                "chat_id": CHAT_ID_OBJECT["region_4"],
                "message_thread_id": 2,
            },
            
            "Kampong Thom": {
                "region": "R5",
                "chat_id": CHAT_ID_OBJECT["region_5"],
                "message_thread_id": 6,
            },
            
            "Siem Reap": {
                "region": "R5",
                "chat_id": CHAT_ID_OBJECT["region_5"],
                "message_thread_id": 2,
            },
            
            "Oddar Meanchey": {
                "region": "R5",
                "chat_id": CHAT_ID_OBJECT["region_5"],
                "message_thread_id": 12,
            },
            
            "Preah Vihear": {
                "region": "R5",
                "chat_id": CHAT_ID_OBJECT["region_5"],
                "message_thread_id": 16,
            },
            
            "Mondol Kiri": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 12,
            },
            
            "Ratanak Kiri": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 10,
            },
            
            "Strung Treng": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 8,
            },
            
            "Kratie": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 6,
            },
            
            "Tbong Khmoum": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 4,
            },
            
            "Kampong Cham": {
                "region": "R6",
                "chat_id": CHAT_ID_OBJECT["region_6"],
                "message_thread_id": 2,
            },    
        
        
    },
}


def get_telegram_route(
    product: str,
    province: str,
) -> dict[str, object]:
    """
    Get Telegram destination for one product/province.
    """

    product_key = str(product).strip().upper()
    province_key = str(province).strip()

    product_routes = TELEGRAM_ROUTES.get(
        product_key
    )

    if product_routes is None:
        raise KeyError(
            f"No Telegram routing exists "
            f"for product: {product_key}"
        )

    route = product_routes.get(
        province_key
    )

    if route is None:
        raise KeyError(
            f"No Telegram routing exists for "
            f"{product_key} / {province_key}"
        )

    return route.copy()