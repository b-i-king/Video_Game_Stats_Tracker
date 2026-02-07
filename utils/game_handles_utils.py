"""
Game Social Media Handles & Hashtags Utility
Centralized repository for game-related social media accounts and hashtags
Supports: Instagram, Twitter

Usage:
    from game_handles_utils import get_game_handle, get_game_hashtags, get_all_game_data
    
    # Get Instagram handle
    handle = get_game_handle('call of duty', 'instagram')
    
    # Get Twitter hashtags
    hashtags = get_game_hashtags('fortnite', 'twitter')
    
    # Get all data for a game on a platform
    data = get_all_game_data('apex legends', 'instagram')
"""

# ============================================================================
# SOCIAL MEDIA GAME HANDLES & HASHTAGS
# ============================================================================

GAME_SOCIAL_DATA = {
    # --- Publishers & Studios ---
    'ad hoc studio': {
        'instagram': {
            'handle': '@theadhocstudio',
            'hashtags': ['#adhocstudio', '#gamedev']
        },
        'twitter': {
            'handle': '@AdHocStudio',
            'hashtags': ['#adhocstudio', '#gamedev']
        }
    },
    'electronic arts': {
        'instagram': {
            'handle': '@ea',
            'hashtags': ['#ea', '#electronicarts']
        },
        'twitter': {
            'handle': '@EA',
            'hashtags': ['#EA', '#ElectronicArts']
        }
    },
    'ea': {
        'instagram': {
            'handle': '@ea',
            'hashtags': ['#ea', '#electronicarts']
        },
        'twitter': {
            'handle': '@EA',
            'hashtags': ['#EA', '#ElectronicArts']
        }
    },
    'activision': {
        'instagram': {
            'handle': '@activision',
            'hashtags': ['#activision', '#callofduty']
        },
        'twitter': {
            'handle': '@Activision',
            'hashtags': ['#Activision', '#CallOfDuty']
        }
    },
    'blizzard': {
        'instagram': {
            'handle': '@blizzard_ent',
            'hashtags': ['#blizzard', '#overwatch']
        },
        'twitter': {
            'handle': '@Blizzard_Ent',
            'hashtags': ['#Blizzard', '#Overwatch']
        }
    },
    'ubisoft': {
        'instagram': {
            'handle': '@ubisoft',
            'hashtags': ['#ubisoft', '#assassinscreed']
        },
        'twitter': {
            'handle': '@Ubisoft',
            'hashtags': ['#Ubisoft', '#AssassinsCreed']
        }
    },
    'bethesda': {
        'instagram': {
            'handle': '@bethesda',
            'hashtags': ['#bethesda', '#fallout']
        },
        'twitter': {
            'handle': '@bethesda',
            'hashtags': ['#Bethesda', '#Fallout']
        }
    },
    'rockstar games': {
        'instagram': {
            'handle': '@rockstargames',
            'hashtags': ['#rockstargames', '#gta']
        },
        'twitter': {
            'handle': '@RockstarGames',
            'hashtags': ['#RockstarGames', '#GTA']
        }
    },
    'nintendo': {
        'instagram': {
            'handle': '@nintendoamerica',
            'hashtags': ['#nintendo', '#nintendoswitch']
        },
        'twitter': {
            'handle': '@NintendoAmerica',
            'hashtags': ['#Nintendo', '#NintendoSwitch']
        }
    },
    'playstation': {
        'instagram': {
            'handle': '@playstation',
            'hashtags': ['#playstation', '#ps5']
        },
        'twitter': {
            'handle': '@PlayStation',
            'hashtags': ['#PlayStation', '#PS5']
        }
    },
    'xbox': {
        'instagram': {
            'handle': '@xbox',
            'hashtags': ['#xbox', '#xboxseriesx']
        },
        'twitter': {
            'handle': '@Xbox',
            'hashtags': ['#Xbox', '#XboxSeriesX']
        }
    },
    'riot games': {
        'instagram': {
            'handle': '@riotgames',
            'hashtags': ['#riotgames', '#leagueoflegends']
        },
        'twitter': {
            'handle': '@riotgames',
            'hashtags': ['#RiotGames', '#LeagueOfLegends']
        }
    },
    'epic games': {
        'instagram': {
            'handle': '@epicgames',
            'hashtags': ['#epicgames', '#fortnite']
        },
        'twitter': {
            'handle': '@EpicGames',
            'hashtags': ['#EpicGames', '#Fortnite']
        }
    },
    'square enix': {
        'instagram': {
            'handle': '@squareenix',
            'hashtags': ['#squareenix', '#finalfantasy']
        },
        'twitter': {
            'handle': '@SquareEnix',
            'hashtags': ['#SquareEnix', '#FinalFantasy']
        }
    },
    'capcom': {
        'instagram': {
            'handle': '@capcom_unity',
            'hashtags': ['#capcom', '#residentevil']
        },
        'twitter': {
            'handle': '@CapcomUSA_',
            'hashtags': ['#Capcom', '#ResidentEvil']
        }
    },
    'cd projekt red': {
        'instagram': {
            'handle': '@cdprojektred',
            'hashtags': ['#cdprojektred', '#cyberpunk2077']
        },
        'twitter': {
            'handle': '@CDPROJEKTRED',
            'hashtags': ['#CDProjektRed', '#Cyberpunk2077']
        }
    },
    'fromsoftware': {
        'instagram': {
            'handle': '@fromsoftware_pr',
            'hashtags': ['#fromsoftware', '#eldenring']
        },
        'twitter': {
            'handle': '@fromsoftware_pr',
            'hashtags': ['#FromSoftware', '#EldenRing']
        }
    },
    'valve': {
        'instagram': {
            'handle': '@valvesoftware',
            'hashtags': ['#valve', '#steam']
        },
        'twitter': {
            'handle': '@valvesoftware',
            'hashtags': ['#Valve', '#Steam']
        }
    },
    'bioware': {
        'instagram': {
            'handle': '@bioware',
            'hashtags': ['#bioware', '#masseffect']
        },
        'twitter': {
            'handle': '@bioware',
            'hashtags': ['#BioWare', '#MassEffect']
        }
    },
    'naughty dog': {
        'instagram': {
            'handle': '@naughty_dog',
            'hashtags': ['#naughtydog', '#thelastofus']
        },
        'twitter': {
            'handle': '@Naughty_Dog',
            'hashtags': ['#NaughtyDog', '#TheLastOfUs']
        }
    },
    'insomniac games': {
        'instagram': {
            'handle': '@insomniacgames',
            'hashtags': ['#insomniacgames', '#spiderman']
        },
        'twitter': {
            'handle': '@insomniacgames',
            'hashtags': ['#InsomniacGames', '#SpiderMan']
        }
    },
    'bungie': {
        'instagram': {
            'handle': '@bungie',
            'hashtags': ['#bungie', '#destiny2']
        },
        'twitter': {
            'handle': '@Bungie',
            'hashtags': ['#Bungie', '#Destiny2']
        }
    },
    
    # --- Popular Franchises & Titles ---
    'call of duty': {
        'instagram': {
            'handle': '@callofduty',
            'hashtags': ['#callofduty', '#warzone', '#cod']
        },
        'twitter': {
            'handle': '@CallofDuty',
            'hashtags': ['#CallOfDuty', '#Warzone', '#COD']
        }
    },
    'warzone': {
        'instagram': {
            'handle': '@callofduty',
            'hashtags': ['#warzone', '#callofduty', '#cod']
        },
        'twitter': {
            'handle': '@CallofDuty',
            'hashtags': ['#Warzone', '#CallOfDuty', '#COD']
        }
    },
    'apex legends': {
        'instagram': {
            'handle': '@playapex',
            'hashtags': ['#apexlegends', '#playapex']
        },
        'twitter': {
            'handle': '@PlayApex',
            'hashtags': ['#ApexLegends', '#PlayApex']
        }
    },
    'fortnite': {
        'instagram': {
            'handle': '@fortnite',
            'hashtags': ['#fortnite', '#fortnitebr']
        },
        'twitter': {
            'handle': '@FortniteGame',
            'hashtags': ['#Fortnite', '#FortniteBR']
        }
    },
    'valorant': {
        'instagram': {
            'handle': '@valorant',
            'hashtags': ['#valorant', '#valorantclips']
        },
        'twitter': {
            'handle': '@VALORANTGame',
            'hashtags': ['#VALORANT', '#ValorantClips']
        }
    },
    'overwatch': {
        'instagram': {
            'handle': '@playoverwatch',
            'hashtags': ['#overwatch2', '#overwatch']
        },
        'twitter': {
            'handle': '@PlayOverwatch',
            'hashtags': ['#Overwatch2', '#Overwatch']
        }
    },
    'overwatch 2': {
        'instagram': {
            'handle': '@playoverwatch',
            'hashtags': ['#overwatch2', '#overwatch']
        },
        'twitter': {
            'handle': '@PlayOverwatch',
            'hashtags': ['#Overwatch2', '#Overwatch']
        }
    },
    'rocket league': {
        'instagram': {
            'handle': '@rocketleague',
            'hashtags': ['#rocketleague', '#rlcs']
        },
        'twitter': {
            'handle': '@RocketLeague',
            'hashtags': ['#RocketLeague', '#RLCS']
        }
    },
    'fifa': {
        'instagram': {
            'handle': '@easportsfifa',
            'hashtags': ['#eafc', '#easportsfc']
        },
        'twitter': {
            'handle': '@EASPORTSFC',
            'hashtags': ['#EAFC', '#EASportsFC']
        }
    },
    'fc 24': {
        'instagram': {
            'handle': '@easportsfc',
            'hashtags': ['#eafc24', '#fc24']
        },
        'twitter': {
            'handle': '@EASPORTSFC',
            'hashtags': ['#EAFC24', '#FC24']
        }
    },
    'fc 25': {
        'instagram': {
            'handle': '@easportsfc',
            'hashtags': ['#eafc25', '#fc25']
        },
        'twitter': {
            'handle': '@EASPORTSFC',
            'hashtags': ['#EAFC25', '#FC25']
        }
    },
    'madden': {
        'instagram': {
            'handle': '@eamaddennfl',
            'hashtags': ['#madden', '#nfl']
        },
        'twitter': {
            'handle': '@EAMaddenNFL',
            'hashtags': ['#Madden', '#NFL']
        }
    },
    'nba 2k': {
        'instagram': {
            'handle': '@nba2k',
            'hashtags': ['#nba2k', '#2k']
        },
        'twitter': {
            'handle': '@NBA2K',
            'hashtags': ['#NBA2K', '#2K']
        }
    },
    'mlb the show': {
        'instagram': {
            'handle': '@mlbtheshow',
            'hashtags': ['#mlbtheshow', '#mlb']
        },
        'twitter': {
            'handle': '@MLBTheShow',
            'hashtags': ['#MLBTheShow', '#MLB']
        }
    },
    'minecraft': {
        'instagram': {
            'handle': '@minecraft',
            'hashtags': ['#minecraft', '#minecraftbuilds']
        },
        'twitter': {
            'handle': '@Minecraft',
            'hashtags': ['#Minecraft', '#MinecraftBuilds']
        }
    },
    'gta': {
        'instagram': {
            'handle': '@rockstargames',
            'hashtags': ['#gtav', '#gta6']
        },
        'twitter': {
            'handle': '@RockstarGames',
            'hashtags': ['#GTAV', '#GTA6']
        }
    },
    'grand theft auto': {
        'instagram': {
            'handle': '@rockstargames',
            'hashtags': ['#gtav', '#gta6']
        },
        'twitter': {
            'handle': '@RockstarGames',
            'hashtags': ['#GTAV', '#GTA6']
        }
    },
    'red dead': {
        'instagram': {
            'handle': '@rockstargames',
            'hashtags': ['#rdr2', '#reddeadredemption']
        },
        'twitter': {
            'handle': '@RockstarGames',
            'hashtags': ['#RDR2', '#RedDeadRedemption']
        }
    },
    'destiny': {
        'instagram': {
            'handle': '@destinythegame',
            'hashtags': ['#destiny2', '#destinythegame']
        },
        'twitter': {
            'handle': '@DestinyTheGame',
            'hashtags': ['#Destiny2', '#DestinyTheGame']
        }
    },
    'destiny 2': {
        'instagram': {
            'handle': '@destinythegame',
            'hashtags': ['#destiny2', '#destinythegame']
        },
        'twitter': {
            'handle': '@DestinyTheGame',
            'hashtags': ['#Destiny2', '#DestinyTheGame']
        }
    },
    'halo': {
        'instagram': {
            'handle': '@halo',
            'hashtags': ['#haloinfinite', '#halo']
        },
        'twitter': {
            'handle': '@Halo',
            'hashtags': ['#HaloInfinite', '#Halo']
        }
    },
    'battlefield': {
        'instagram': {
            'handle': '@battlefield',
            'hashtags': ['#battlefield', '#fps']
        },
        'twitter': {
            'handle': '@Battlefield',
            'hashtags': ['#Battlefield', '#FPS']
        }
    },
    'fallout': {
        'instagram': {
            'handle': '@fallout',
            'hashtags': ['#fallout', '#fallout4']
        },
        'twitter': {
            'handle': '@Fallout',
            'hashtags': ['#Fallout', '#Fallout4']
        }
    },
    'elder scrolls': {
        'instagram': {
            'handle': '@elderscrolls',
            'hashtags': ['#elderscrolls', '#skyrim']
        },
        'twitter': {
            'handle': '@ElderScrolls',
            'hashtags': ['#ElderScrolls', '#Skyrim']
        }
    },
    'skyrim': {
        'instagram': {
            'handle': '@elderscrolls',
            'hashtags': ['#skyrim', '#elderscrolls']
        },
        'twitter': {
            'handle': '@ElderScrolls',
            'hashtags': ['#Skyrim', '#ElderScrolls']
        }
    },
    'dark souls': {
        'instagram': {
            'handle': '@darksouls',
            'hashtags': ['#darksouls', '#fromsoftware']
        },
        'twitter': {
            'handle': '@DarkSoulsGame',
            'hashtags': ['#DarkSouls', '#FromSoftware']
        }
    },
    'elden ring': {
        'instagram': {
            'handle': '@eldenring',
            'hashtags': ['#eldenring', '#fromsoftware']
        },
        'twitter': {
            'handle': '@ELDENRING',
            'hashtags': ['#ELDENRING', '#FromSoftware']
        }
    },
    'resident evil': {
        'instagram': {
            'handle': '@residentevil',
            'hashtags': ['#residentevil', '#capcom']
        },
        'twitter': {
            'handle': '@RE_Games',
            'hashtags': ['#ResidentEvil', '#Capcom']
        }
    },
    'street fighter': {
        'instagram': {
            'handle': '@streetfighter',
            'hashtags': ['#streetfighter', '#sf6']
        },
        'twitter': {
            'handle': '@StreetFighter',
            'hashtags': ['#StreetFighter', '#SF6']
        }
    },
    'mortal kombat': {
        'instagram': {
            'handle': '@mortalkombat',
            'hashtags': ['#mortalkombat', '#mk1']
        },
        'twitter': {
            'handle': '@MortalKombat',
            'hashtags': ['#MortalKombat', '#MK1']
        }
    },
    'tekken': {
        'instagram': {
            'handle': '@tekken',
            'hashtags': ['#tekken', '#tekken8']
        },
        'twitter': {
            'handle': '@Tekken',
            'hashtags': ['#TEKKEN', '#TEKKEN8']
        }
    },
    'league of legends': {
        'instagram': {
            'handle': '@leagueoflegends',
            'hashtags': ['#leagueoflegends', '#lol']
        },
        'twitter': {
            'handle': '@LeagueOfLegends',
            'hashtags': ['#LeagueOfLegends', '#LoL']
        }
    },
    'dota': {
        'instagram': {
            'handle': '@dota2',
            'hashtags': ['#dota2', '#dota']
        },
        'twitter': {
            'handle': '@DOTA2',
            'hashtags': ['#Dota2', '#Dota']
        }
    },
    'counter-strike': {
        'instagram': {
            'handle': '@counterstrike',
            'hashtags': ['#cs2', '#counterstrike']
        },
        'twitter': {
            'handle': '@CounterStrike',
            'hashtags': ['#CS2', '#CounterStrike']
        }
    },
    'csgo': {
        'instagram': {
            'handle': '@counterstrike',
            'hashtags': ['#cs2', '#counterstrike']
        },
        'twitter': {
            'handle': '@CounterStrike',
            'hashtags': ['#CS2', '#CounterStrike']
        }
    },
    'cs2': {
        'instagram': {
            'handle': '@counterstrike',
            'hashtags': ['#cs2', '#counterstrike']
        },
        'twitter': {
            'handle': '@CounterStrike',
            'hashtags': ['#CS2', '#CounterStrike']
        }
    },
    'rainbow six': {
        'instagram': {
            'handle': '@rainbow6game',
            'hashtags': ['#rainbow6', '#r6siege']
        },
        'twitter': {
            'handle': '@Rainbow6Game',
            'hashtags': ['#Rainbow6', '#R6Siege']
        }
    },
    'pubg': {
        'instagram': {
            'handle': '@pubg',
            'hashtags': ['#pubg', '#pubgmobile']
        },
        'twitter': {
            'handle': '@PUBG',
            'hashtags': ['#PUBG', '#PUBGMobile']
        }
    },
    'warframe': {
        'instagram': {
            'handle': '@playwarframe',
            'hashtags': ['#warframe', '#tenno']
        },
        'twitter': {
            'handle': '@PlayWarframe',
            'hashtags': ['#Warframe', '#Tenno']
        }
    },
    'diablo': {
        'instagram': {
            'handle': '@diablo',
            'hashtags': ['#diablo4', '#diablo']
        },
        'twitter': {
            'handle': '@Diablo',
            'hashtags': ['#Diablo4', '#Diablo']
        }
    },
    'world of warcraft': {
        'instagram': {
            'handle': '@warcraft',
            'hashtags': ['#warcraft', '#worldofwarcraft']
        },
        'twitter': {
            'handle': '@Warcraft',
            'hashtags': ['#Warcraft', '#WorldOfWarcraft']
        }
    },
    'starcraft': {
        'instagram': {
            'handle': '@starcraft',
            'hashtags': ['#starcraft', '#starcraft2']
        },
        'twitter': {
            'handle': '@StarCraft',
            'hashtags': ['#StarCraft', '#StarCraft2']
        }
    },
    'sims': {
        'instagram': {
            'handle': '@thesims',
            'hashtags': ['#thesims', '#sims4']
        },
        'twitter': {
            'handle': '@TheSims',
            'hashtags': ['#TheSims', '#Sims4']
        }
    },
    'animal crossing': {
        'instagram': {
            'handle': '@animalcrossing',
            'hashtags': ['#animalcrossing', '#acnh']
        },
        'twitter': {
            'handle': '@animalcrossing',
            'hashtags': ['#AnimalCrossing', '#ACNH']
        }
    },
    'zelda': {
        'instagram': {
            'handle': '@zelda',
            'hashtags': ['#zelda', '#legendofzelda']
        },
        'twitter': {
            'handle': '@NintendoAmerica',
            'hashtags': ['#Zelda', '#LegendOfZelda']
        }
    },
    'pokemon': {
        'instagram': {
            'handle': '@pokemon',
            'hashtags': ['#pokemon', '#nintendo']
        },
        'twitter': {
            'handle': '@Pokemon',
            'hashtags': ['#Pokemon', '#Nintendo']
        }
    },
    'super smash bros': {
        'instagram': {
            'handle': '@smashbrosus',
            'hashtags': ['#smashbros', '#supersmashbros']
        },
        'twitter': {
            'handle': '@SmashBrosUS',
            'hashtags': ['#SmashBros', '#SuperSmashBros']
        }
    },
    'mario kart': {
        'instagram': {
            'handle': '@mariokart',
            'hashtags': ['#mariokart', '#nintendo']
        },
        'twitter': {
            'handle': '@mariokarttour',
            'hashtags': ['#MarioKart', '#Nintendo']
        }
    },
    'splatoon': {
        'instagram': {
            'handle': '@splatoon',
            'hashtags': ['#splatoon', '#splatoon3']
        },
        'twitter': {
            'handle': '@SplatoonNA',
            'hashtags': ['#Splatoon', '#Splatoon3']
        }
    },
    'god of war': {
        'instagram': {
            'handle': '@santamonicastu',
            'hashtags': ['#godofwar', '#ragnarok']
        },
        'twitter': {
            'handle': '@SonySantaMonica',
            'hashtags': ['#GodOfWar', '#Ragnarok']
        }
    },
    'spider-man': {
        'instagram': {
            'handle': '@insomniacgames',
            'hashtags': ['#spidermanps5', '#marvel']
        },
        'twitter': {
            'handle': '@insomniacgames',
            'hashtags': ['#SpiderManPS5', '#Marvel']
        }
    },
    'last of us': {
        'instagram': {
            'handle': '@naughty_dog',
            'hashtags': ['#thelastofus', '#tlou']
        },
        'twitter': {
            'handle': '@Naughty_Dog',
            'hashtags': ['#TheLastOfUs', '#TLOU']
        }
    },
    'uncharted': {
        'instagram': {
            'handle': '@naughty_dog',
            'hashtags': ['#uncharted', '#naughtydog']
        },
        'twitter': {
            'handle': '@Naughty_Dog',
            'hashtags': ['#Uncharted', '#NaughtyDog']
        }
    },
    'horizon': {
        'instagram': {
            'handle': '@guerrilla',
            'hashtags': ['#horizonforbiddenwest', '#playstation']
        },
        'twitter': {
            'handle': '@Guerrilla',
            'hashtags': ['#HorizonForbiddenWest', '#PlayStation']
        }
    },
    'ghost of tsushima': {
        'instagram': {
            'handle': '@suckerpunchprod',
            'hashtags': ['#ghostoftsushima', '#suckerpunch']
        },
        'twitter': {
            'handle': '@SuckerPunchProd',
            'hashtags': ['#GhostOfTsushima', '#SuckerPunch']
        }
    },
    'final fantasy': {
        'instagram': {
            'handle': '@finalfantasy',
            'hashtags': ['#finalfantasy', '#ff7r']
        },
        'twitter': {
            'handle': '@FinalFantasy',
            'hashtags': ['#FinalFantasy', '#FF7R']
        }
    },
    'monster hunter': {
        'instagram': {
            'handle': '@monsterhunter',
            'hashtags': ['#monsterhunter', '#mhwilds']
        },
        'twitter': {
            'handle': '@monsterhunter',
            'hashtags': ['#MonsterHunter', '#MHWilds']
        }
    },
    'dragon ball': {
        'instagram': {
            'handle': '@dragonballgames',
            'hashtags': ['#dragonball', '#dbz']
        },
        'twitter': {
            'handle': '@dragonballgames',
            'hashtags': ['#DragonBall', '#DBZ']
        }
    },
    'naruto': {
        'instagram': {
            'handle': '@narutogames',
            'hashtags': ['#naruto', '#anime']
        },
        'twitter': {
            'handle': '@BandaiNamcoUS',
            'hashtags': ['#Naruto', '#Anime']
        }
    },
    'one piece': {
        'instagram': {
            'handle': '@onepiecegames',
            'hashtags': ['#onepiece', '#anime']
        },
        'twitter': {
            'handle': '@BandaiNamcoUS',
            'hashtags': ['#OnePiece', '#Anime']
        }
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_game_handle(game_name, platform='instagram'):
    """
    Get the social media handle for a game on a specific platform.
    
    Args:
        game_name: str (case-insensitive game name)
        platform: str ('instagram' or 'twitter')
    
    Returns:
        str: Handle (e.g., '@callofduty') or None if not found
    
    Examples:
        >>> get_game_handle('Call of Duty', 'instagram')
        '@callofduty'
        >>> get_game_handle('fortnite', 'twitter')
        '@FortniteGame'
    """
    game_name_lower = game_name.lower()
    
    if game_name_lower in GAME_SOCIAL_DATA:
        platform_data = GAME_SOCIAL_DATA[game_name_lower].get(platform, {})
        return platform_data.get('handle')
    
    return None


def get_game_hashtags(game_name, platform='instagram'):
    """
    Get the hashtags for a game on a specific platform.
    
    Args:
        game_name: str (case-insensitive game name)
        platform: str ('instagram' or 'twitter')
    
    Returns:
        list: List of hashtags (e.g., ['#callofduty', '#warzone']) or empty list
    
    Examples:
        >>> get_game_hashtags('apex legends', 'instagram')
        ['#apexlegends', '#playapex']
        >>> get_game_hashtags('valorant', 'twitter')
        ['#VALORANT', '#ValorantClips']
    """
    game_name_lower = game_name.lower()
    
    if game_name_lower in GAME_SOCIAL_DATA:
        platform_data = GAME_SOCIAL_DATA[game_name_lower].get(platform, {})
        return platform_data.get('hashtags', [])
    
    return []


def get_all_game_data(game_name, platform='instagram'):
    """
    Get all social media data (handle + hashtags) for a game on a platform.
    
    Args:
        game_name: str (case-insensitive game name)
        platform: str ('instagram' or 'twitter')
    
    Returns:
        dict: {'handle': str, 'hashtags': list} or None if not found
    
    Examples:
        >>> get_all_game_data('fortnite', 'twitter')
        {'handle': '@FortniteGame', 'hashtags': ['#Fortnite', '#FortniteBR']}
    """
    game_name_lower = game_name.lower()
    
    if game_name_lower in GAME_SOCIAL_DATA:
        return GAME_SOCIAL_DATA[game_name_lower].get(platform)
    
    return None


def format_caption_with_game_data(game_name, platform='instagram', include_handle=True, include_hashtags=True):
    """
    Generate formatted text with game handle and/or hashtags.
    
    Args:
        game_name: str (case-insensitive game name)
        platform: str ('instagram' or 'twitter')
        include_handle: bool (include @handle)
        include_hashtags: bool (include #hashtags)
    
    Returns:
        str: Formatted text (e.g., "@callofduty #callofduty #warzone") or empty string
    
    Examples:
        >>> format_caption_with_game_data('valorant', 'twitter')
        '@VALORANTGame #VALORANT #ValorantClips'
        >>> format_caption_with_game_data('apex legends', 'instagram', include_handle=False)
        '#apexlegends #playapex'
    """
    parts = []
    
    if include_handle:
        handle = get_game_handle(game_name, platform)
        if handle:
            parts.append(handle)
    
    if include_hashtags:
        hashtags = get_game_hashtags(game_name, platform)
        if hashtags:
            parts.extend(hashtags)
    
    return ' '.join(parts)


def get_supported_games():
    """
    Get list of all supported game names.
    
    Returns:
        list: List of game names (lowercase)
    """
    return list(GAME_SOCIAL_DATA.keys())


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test some examples
    print("Testing game_handles_utils.py\n")
    
    test_games = ['call of duty', 'fortnite', 'valorant', 'apex legends']
    
    for game in test_games:
        print(f"Game: {game}")
        print(f"  Instagram: {format_caption_with_game_data(game, 'instagram')}")
        print(f"  Twitter:   {format_caption_with_game_data(game, 'twitter')}")
        print()
    
    print(f"Total games supported: {len(get_supported_games())}")