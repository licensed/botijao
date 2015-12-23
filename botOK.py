#-*- coding:utf-8 -*-

import sys
import lxml.html
from collections import defaultdict
from twisted.internet import reactor, task, defer, protocol
from twisted.internet.task import LoopingCall
from twisted.python import log
from twisted.words.protocols import irc
from twisted.web import xmlrpc, client
from twisted.application import internet, service
import urllib
import urllib2
from bs4 import BeautifulSoup
from datetime import datetime
import httplib, os
from json import load
import feedparser
from time import strftime
from os.path import isfile
#from threading import Timer
#twisted.web.client.downloadPage
#twisted.web.client.getPage
x = datetime.now()
hoje = x.strftime('%d/%m/%Y')
HOST, PORT = 'irc.irchighway.net', 6667
MINUTES = 60.0
bpaste = xmlrpc.Proxy('http://bpaste.net/xmlrpc/', allowNone=True)

def slicedict(d, s):
    return {k:v for k,v in d.iteritems() if k.startswith(s)}


class MeuPrimeiroProtocoloIRC(irc.IRCClient):
    nickname = 'BOTijao'
    _termos = defaultdict(list)
    lineRate = 0.5
    fonte = None
    fonte_url = None
    
    def signedOn(self):
        # Este método é chamado automaticamente após o login, quando o servidor
        # reconhece o usuário e nick do bot
        self.msg("nickserv","identify default")        
        # Entra nos canais definidos na factory:
        for canal in self.factory.canais:
            self.join(canal)
        #repeater = LoopingCall(self.comando_cams("#cam4lic","resto"))
        #repeater.start(1 * MINUTES)
        #t = Timer(600.0, self.comando_cams,["#cam4","resto"])
        #t.start()

    # Este método roda quando uma PRIVMSG é recebida do servidor
    def privmsg(self, usuario, canal, mensagem):
        nick, sep, host = usuario.partition('!')       
        if 'imgur.com/a/' in mensagem:
            temp = mensagem.split()
            for x in temp:
                if 'imgur.com/a/' in x:
                    link = x
                    break
            try:        
                pagina = urllib2.urlopen(link)
                conteudo = BeautifulSoup(pagina.read())
            except:
                return ["Falhou ao ler a pagina"]
            
            fotos = conteudo.findAll('div', attrs = {'class' : 'image'})
            baixou = False
            for i in fotos:
                foto = "http:" + str(i.find('a').get('href'))
                nome = "/home/licensed/pootz/" + str(foto[-5:len(foto)-12:-1]) + ".jpg" #str(foto.split("/")[3])
                if isfile(nome):
                    self._manda_mensagem(["Já tenho essa foto!"], canal)                          
                    break
                else:
                    urllib.urlretrieve(link,nome)
                    baixou = True
            if baixou:
                self._manda_mensagem(["Galeria Baixada"], canal)

        #mensagem = mensagem.strip()
        # Capturar fotinhas =D
        elif 'jpg' in mensagem or 'png' in mensagem:
            temp=mensagem.split()
            for x in temp:
                if 'jpg' in x or 'png' in x or 'jpeg' in x:
                    link=x
            nomearq = str(link[-5:len(link)-12:-1]) + ".jpg"
            nome="/home/licensed/pootz/" + nomearq
            if not isfile(nome):
                urllib.urlretrieve(link,nome)
        elif not mensagem.startswith('!'): # se não for um comando trigger
            return # não faz nada
        comando, sep, resto = mensagem.lstrip('!').partition(' ')
        # Pega a função equivalente ao comando executado
        func = getattr(self, 'comando_' + comando, None)
        # Ou, se não tiver nenhuma função, ignora a mensagem
        if func is None:
            return
        # tenta decodificar o resto da mensagem para unicode. Infelizmente,
        # o protocolo IRC não possui uma forma de indicar o encoding usado
        # nas mensagens, então é um chute.
        try:
            resto = resto.decode('utf-8') # tentamos utf-8
        except UnicodeDecodeError:
            resto = resto.decode('latin1') # se falhar usamos latin1
        # maybeDeferred significa algo como "talvezDeferred".
        # maybeDeferred sempre retorna um Deferred. Esta linha vai tentar
        # executar func(resto) e se isso retornar um deferred, resolvido, caso
        # contrario vai retornar o valor de retorno da funcao envolvido em
        # defer.succeed. Caso tenha um erro, envolve em defer.fail.
        d = defer.maybeDeferred(func, canal, resto)
        # Adiciona callbacks ao deferred para lidar com qualquer que seja o resultado.
        # addErrback significa "chame isso se der erro"
        # Se o comando der algum erro, o _show_error vai transformar o erro em
        # uma mensagem de erro compacta primeiro:
        d.addErrback(self._mostra_erro)
        # O que isso retornar é enviado como resposta. addCallback significa
        # "chame _manda_mensagem quando o Deferred disparar":
        if canal == self.nickname:
            # Quando canal == self.nickname, a mensagem foi enviada diretamente
            # para o bot e não para o canal, então a resposta tbm vai direto 
            # para quem mandou:
            d.addCallback(self._manda_mensagem, nick)
        else:
            # Caso contrário, manda a resposta para o canal, e usa o nick 
            # como endereçamento na própria mensagem:
            d.addCallback(self._manda_mensagem, canal)
    #def _manda_mensagem(self, target, nick=None):
        #def callback(msg):
            #if nick:
                #msg = '%s' % (msg)
                ##msg = '%s, %s' % (nick, msg)
            #self.msg(target, msg)
        #return callback


    def _manda_mensagem(self, msgs, target, nick=None):
        for msg in msgs:
            # Como os métodos de comando do bot sempre retornam unicode e unicode precisa ser
            # encodificado pra ser transmitido, é necessário encodificar as mensagens.
            # Infelizmente o protocolo IRC veio antes de existir unicode então
            # não existe uma forma correta de especificar qual encoding é usado
            # para os dados transmitidos neste protocolo. UTF-8 é o melhor chute
            # e é o que a maioria das pessoas usa.
            msg = msg.encode('utf-8')
            if nick:
                msg = '%s' % (msg)
            self.msg(target, msg)

    def _mostra_erro(self, failure):
        return [failure.getErrorMessage()]

    def comando_ping(self, canal, resto):
        u"""Pra ver se está respondendo"""
        return ['Pong.']

    def comando_depois(self, canal, resto):
        u"""Diz algo depois de um tempo - sintaxe: depois [tempo em segundos] [frase]"""
        quando, sep, msg = resto.partition(' ')
        quando = int(quando)
        d = defer.Deferred()
        # Um pequeno exemplo de como atrasar a resposta de um comando. callLater 
        # vai disparar o callback do deferred quando o tempo "quando" passar
        reactor.callLater(quando, d.callback, [msg])
        # Retornar o deferred aqui significa que ele será retornado pelo
        # maybeDeferred no método privmsg acima. Quando o tempo passar
        # e ele for disparado, [msg] irá para o callback _manda_mensagem
        return d

    def comando_titulo(self, canal, url):
        u"""Mostra o título de uma página web. Sintaxe: titulo [url]"""
        # Outro exemplo de uso de Deferreds. 
        d = client.getPage(url.encode('utf-8'))
        # getPage retorna um Deferred. Quando a pagina acabar de baixar, vai
        # executar o callback abaixo. Assim o bot pode continuar respondendo
        # outras coisas enquanto a pagina nao chega.
        # se a gente não adicionasse o callback _extrai_titulo aqui e retornasse
        # o deferred simplesmente, iria funcionar do mesmo jeito, mas o resultado
        # que iria para _manda_mensagem seria a página toda.
        d.addCallback(self._extrai_titulo, url)
        return d

    def _extrai_titulo(self, pagina, url):
        # Parseia a página em uma árvore de elementos html
        elementos = lxml.html.fromstring(pagina)
        # Extrai o título da página usando xpath
        titulo = u' '.join(elementos.xpath('//title/text()')).strip()
        # como ja estamos num callback aqui (criado em comando_titulo),
        # a resposta sera passada para o proximo callback que tiver sido
        # adicionado na mensagem (_manda_mensagem)
        if not titulo:
            titulo = u'Sem título'
        return [u'{0} -- {1}'.format(url, titulo)]

    def comando_aprenda(self, canal, resto):
        u"""Aprende alguma coisa. Sintaxe: aprenda [termo] > [frase]"""
        termo, sep, resto = resto.partition('>')
        termo = termo.strip()
        resto = resto.strip()
        if sep and resto:
            self._termos[termo].append(resto)
            return [u"Obrigado, aprendi mais uma! [{0}]".format(len(self._termos[termo]))]
        else:
            return [u'Aprender o quê? Você não mandou nada']

    def comando_diga(self, canal, resto):
        u"""Repete o que foi aprendido. Sintaxe: diga [termo]"""
        resto = resto.strip()
        resp = self._termos.get(resto, None)
        if resp:
            virgula = ', '.join(resp[:-1])
            if virgula:
                return [u'{virgula} e {ultimo}!'.format(
                    termo=resto, virgula=virgula, ultimo=resp[-1])]
            else:
                return [u'{resultado}'.format(
                    termo=resto, resultado=' e '.join(resp))]
        else:
            return [resto]

    def comando_esqueca(self, canal, resto):
        u"""Esquece algo aprendido. Sintaxe: esqueca [termo] [posição]"""
        termo, sep, pos = resto.rpartition(' ')
        pos = int(pos)
        termo = termo.strip()
        del self._termos[termo][pos-1]
        return [u"Já esqueci completamente! [{0}]".format(len(self._termos[termo]))]

    def comando_ajuda(self, canal, resto):
        u"""Mostra a ajuda. Sintaxe !ajuda [comando]"""
        resto = resto.strip()
        if resto:
            return [u'{0} -- {1}'.format(resto, getattr(self, 'comando_' + resto).__doc__)]
        else:
            return [u"Sei os comandos: {0}".format(', '.join(cmd.split('_', 1)[1]
               for cmd in dir(self) if cmd.startswith('comando_')))]

    def _pastebin_criaurl(self, id):
        return ['http://bpaste.net/show/' + id]

    def _pastebin(self, code, lang='python', parent_id=None, filename='',
                 mimetype='text/x-python', private=False):
        """
        Cola algo no pastebin chamando a API do pocoo. 
        http://paste.pocoo.org/help/api/
        """
        d = bpaste.callRemote('pastes.newPaste', lang, code, parent_id, filename,
            mimetype, private)
        d.addCallback(self._pastebin_criaurl)
        return d

    def _fonteurl_configure(self, url):
        self.fonte_url = url
        return [url]

    def comando_fonte(self, canal, linhas):
        u"""Pega uma linha do codigo fonte - Sintaxe: fonte [número da linha]"""
        if not self.fonte:
            self.fonte = open(__file__.rstrip('co')).readlines()
        if linhas:
            if ':' in linhas:
                linhas = [int(linha) for linha in linhas.split(':')]
                linhas = slice(*linhas)
                linhas = self.fonte[linhas]
                return [linha.rstrip().decode('utf-8') for linha in linhas]
            else:
                return [self.fonte[int(linhas)].rstrip().decode('utf-8')]
        else:
            if self.fonte_url:
                return [self.fonte_url]
            else:
                d = self._pastebin(''.join(self.fonte))
                d.addCallback(self._fonteurl_configure)
                return d

    def comando_ola(self, canal, resto):
        u'''Mostra o texto de exemplo a alguem.'''
        msgs = [
            u'Olá! Sou {0}, o bot do licensed.'.format(self.nickname),
            u'Use o comando !ajuda para ver o que posso fazer!'
        ]
        return msgs
    
    def comando_link(self, canal, resto):
        linke=resto[::-1].split("=lru?")
        return [linke[0]]
        
    def comando_encurta(self, canal, resto):
        url = "http://api.adf.ly/api.php?key=ed9f2ecc1a74e476058bb13660e3bf96&uid=164324&advert_type=int&url=" + resto
        f = urllib2.urlopen(url)
        contents = f.read()
        f.close()
        return contents        
    
    def comando_airmail(self, canal, resto):
        return airmail(resto)

    def comando_qtd(self, canal, resto):
        return len(os.listdir('/home/licensed/pootz'))

    def comando_ison(self, canal, resto):
        return ison(resto)    

    def comando_tv(self, canal, resto):
        return tv2(resto)
    
    def comando_tempo(self, canal, resto):
        return tempo(resto)

    def comando_entra(self, canal, resto):
        return self.join(str(resto))
    
    def comando_sai(self, canal, resto):
        return self.part(str(resto))

    def comando_cam4(self, canal, resto):
        return cam4(resto)

    #def comando_iniciacam(self,canal, resto):
        #repeater = LoopingCall(self.comando_cams,["#cam4lic","resto"])
        #repeater.start(1 * MINUTES)
        #t = Timer(600.0, self.comando_cams,["#cam4","resto"])
        #t.start()

    def comando_cams(self, canal, resto):
        lis=[]
        g=open("listacam4.txt","r")
        for linha in g:
            if cam4lote(linha):
                self._manda_mensagem([linha], canal)
                lis.append(linha)
        lis.append("Fim!")
        g.close()
        #if resto == "resto":
            #t.cancel()
            #t = Timer(600.0, self.comando_cams,["#cam4","resto"])
            #t.start()
        return lis
    
    def comando_addcam4(self, canal, resto):
        f = open("listacam4.txt","r")
        for cam in f:
            if resto in cam:
                return [resto + " ja foi adicionado"]
                break
        f.close()
        f = open("listacam4.txt","a")
        if "www" in resto:
            f.write(resto + "\n")
        else:
            f.write("http://www.cam4.com/" + resto + "\n")
        return [resto + " adicionado com sucesso"]


    def comando_addcam(self, canal, resto):
        f = open("listacam4.txt","r")
        for cam in f:
            if resto in cam:
                return [resto + " ja foi adicionado"]
                break
        f.close()
        f = open("listacam4.txt","a")
        if "www" in resto:
            f.write(resto + "\n")
        else:
            f.write("http://www.cam4.com/" + resto + "\n")
        return [resto + " adicionado com sucesso"]
    

def ison(site):
    conn = httplib.HTTPConnection(site)
    conn.request("HEAD", "/")
    r1 = conn.getresponse()
    if (r1.reason == "Found"):
        return ["Online " + site]
    else:
        return ["Offline " + site]

def airmail(x):
    cny = (10*float(x) * 10*float(x) + 20) * 0.45 + 8
    usd = cny*0.154
    return "%s CNY = %s USD" % (cny,usd)

def tv(canal):
    hr = datetime.now().today().hour
    #Operadora SKY=14 CLARO=24
    operadora = 24
    url="http://www.hagah.com.br/programacao-tv/jsp/default.jsp?uf=1&local=1&regionId=1&action=programacao_canal&canal=%s&operadora=%s&data=%s" % (canal,operadora,hoje)
    pagina = urllib2.urlopen(url)
    conteudo = BeautifulSoup(pagina.read(), from_encoding="iso-8858-1")
    tabela = conteudo.findAll(id='grade canal')
    linhas = conteudo.findAll('tr')
    dic={}
    msgs=[]
    cont = 0
    for linha in linhas: 
        dado = linha.findAll('td')
        hora = dado[0]
        if dado[1].findAll('strong'):
            programa=dado[1].findAll('strong')
            for item in programa:
                if item:
                    if hr <= int(hora.contents[0].split(':')[0]):
                        if cont < 5:
                            cont += 1
                            #dic[hora.contents[0]]=item.contents[0]
                            msgs.append(u"%s | %s \n" % (hora.contents[0],item.contents[0]))
    return msgs#.encode("utf8")  

def cam4(login):
    if login:
        site = "http://www.cam4.com/" + login
        pagina = urllib2.urlopen(site)
        conteudo = BeautifulSoup(pagina.read())
        on = conteudo.findAll(id='broadcastingApp')
        if len(on) > 0:
            return ["http://www.cam4.com/" + login + " Online"]
        else:
            return [login + " Offline"]
        
        
def cam4lote(site):
    pagina = urllib2.urlopen(site)
    try:
        conteudo = BeautifulSoup(pagina.read())
    except:
        return None
    on = conteudo.findAll(id='broadcastingApp')
    if len(on) > 0:
        return site
    
def tv2(canal):
    #hr = datetime.now().time().isoformat()[:5]
    hr = strftime("%H:%M")
    dt = strftime("%d/%y")
    canais = {"DISCOVERY HD": "2938", "SKY": "522", "ESPN": "296", "E!": "291", "SKY 126": "426", "GLOBO BH": "311", "TRU TV HD": "467", "SIC": "415", "SKY 131": "429", "ESPN BRASIL": "297", "REDE VIDA": "395", "AXN": "237", "CANAL RURAL": "255", "HISTORY CHANNEL": "329", "TV SENADO": "478", "TELECINE TOUCH HD": "5778", "Mundi Rock": "6642", "RIT": "400", "SPORTV HD": "5118", "Radio Globo RJ": "3526", "TV GLOBO CUIABA": "3325", "RAI": "387", "GLOBO NATAL": "3326", "TV5 MONDE": "485", "ESPN+ HD": "2690", "SPORTV 2 HD": "5117", "GLOBO RJ": "316", "BANDSPORTS2 HD": "4336", " TV TEM - SAO JOSE DO RIO PRETO ": "479", "Kids": "339", "OFF": "5753", "HISTORY CHANNEL HD": "460", "NATIONAL GEOGRAPHIC  ": "367", "APARECIDA": "6882", "GLOBO BAHIA": "310", "Sportv 3": "497", "HBO HD": "4437", "Standards": "445", "NICKELODEON": "370", "GLOBO NEWS HD ": "5774", "MAX PRIME": "348", "SEX ZONE": "410", "DISCOVERY KIDS": "284", "SONY": "436", "BANDSPORTS2": "4316", "ID": "2677", "CANCAO NOVA": "257", "GLOBO SP": "317", "SPORTS+ HD": "3189", "MAX": "345", "POLISHOP": "376", "PLAY TV": "374", "EPTV CAMP.": "294", "BANDEIRANTES": "391", "BAND": "391", "FUTURA": "305", "PREMIERE COMBATE": "278", "COMBATE": "278", "AXN HD": "238", "HBO PLUS": "325", "SEX ZONE HD": "411", "HUSTLER": "330", "GLOBO BRASILIA": "5557", "CENTRO AMERICA": "5627", "PLAYBOY": "375", "GLOBO RECIFE": "315", "INT TV CABUGI": "5553", "PLAYBOY TV": "5794", "TV VANGUARDA": "2679", "TV CULTURA": "471", "TV JUSTICA": "475", "MIX TV": "6881", "BLOOMBERG": "245", "GLOBO DF": "3324", "CineBrasilTV": "3033", "FOX NatGeo HD": "303", "RECORD NEWS": "6883", "SONY HD": "437", "THE GOLF CHANNEL": "459", "CINEMAX": "274", "SPACE HD": "440", "BANDSPORTS": "243", "TNT HD": "463", "GLOOB HD": "1175", "FOX SPORTS HD": "924", "TC PREMIUM HD": "456", "HBO": "4382", "TCM": "448", "FOX SPORTS": "441", "TC CULT": "2672", "TV TRIBUNA SANTOS": "482", "UNIVERSAL CHANNEL HD": "5776", "VERDES MARES": "383", "Peugeot": "3998", "BAND SP": "240", "REDE RECORD": "393", "FOX": "301", "CARTOON NETWORK": "259", "Arte 1": "2855", "RECORD SP": "389", "GNT HD": "2937", "REDE TV": "394", "RFI": "398", "MULTISHOW": "361", "MEGAPIX": "351", "MAX PRIME-e": "349", "DISCOVERY HOME & HEALTH HD": "5780", "RBS - RS ": "388", "TBS": "3312", "WARNER": "461", "MGM": "352", "STUDIO UNIVERSAL": "446", "TELECINE PREMIUM": "455", "GLITZ": "308", "SESCTV": "409", "MAX HD": "347", "MGM HD": "353", "DISNEY CHANNEL HD ": "2668", "TV RATIMBUM": "379", "TV ESPANHOLA": "473", "FX": "306", "FOX LIFE": "302", "ESPN BRASIL HD": "2322", "TV TEM - BAURU": "480", "S.O.D": "5684", "+ GLOBOSAT": "5752", "SONY SPIN": "438", "TV BRASIL": "469", "TV TEM - SOROCABA": "481", "HBO2": "327", "TELECINE ACTION": "449", "TELECINE TOUCH": "457", "GNT": "319", "UNIVERSAL CHANNEL": "486", "PREMIERE 24H": "377", "NBR": "368", "SKY HD": "976", "ANIMAL PLANET": "231", "SBT SP": "407", "GLOBO BELEM": "476", "COMEDY CENTRAL": "2682", "True Blood": "4531", "WOOHOO": "2698", "CANAL BRASIL": "253", "TC PIPOCA HD": "2675", "HBO PLUS": "326", "TERRA VIVA": "458", "TC FUN": "2671", "Nat Geo Wild HD": "365", "EPTV CAMPINAS": "5558", "CNN INTERNACIONAL": "2678", "TC ACTION HD": "450", "OFF HD": "2669", "DEUTSCHE WELLE": "280", "BOA VONTADE TV": "247", "TLC": "287", "TRU TV": "466", "RPC CURITIBA": "403", "MULTISHOW HD": "362", "HBO FAMILY": "322", "GLOBO SAO PAULO": "309", "Disney Channel": "312", "VIVA": "491", "HBO HD": "324", "BANDNEWS": "241", "SBT": "406", "BIS HD": "2710", "MAX HD ": "346", "GLOBO RECIFE": "5818", "TNT": "462", "SYFY": "447", "TELECINE FUN HD": "2939", "BBC WORLD": "244", "SPORTV": "443", "TV GLOBO SP": "474", "A&E;": "230", "CBI": "260", "SEXY HOT": "412", "TC PIPOCA": "2676", "TC TOUCH HD": "5838", "PREMIERE FC HD": "420", "CULTURA SP": "279", "BIO HD": "990", "DISNEY XD": "290", "TV TEM BAURU": "5814", "TELECINE CULT.": "451", "SPORTV 2": "444", "SPORTV 3": "2691", "CINE SKY": "535", "TV NOVO TEMPO": "477", "NICKELODEON HD": "371", "DISCOVERY CHANNEL": "282", "GLOBO NEWS": "314", "COMEDY CENTRAL": "490", "HBO SIGNATURE": "323", "NHK": "369", "VH1 HD": "489", "GLOBO - SP ": "3524", "WARNER HD": "492", "TV ANHANGUERA GOIANIA": "5311", "TV AMAZONAS": "5320", "BIS": "3307", "CINEBRASIL TV": "275", "DISCOVERY HOME & HEALTH": "283", "+GLOBOSAT HD": "2680", "CANAL 21": "256", "SPACE": "439", "TLC HD": "286", "GLOOB": "2936", "DISCOVERY THEATER HD": "2925", "REDETV SP": "396", "MEGAPIX HD": "5777", "TV LIBERAL BELEM": "5579", "SPORTS+": "3161", "TV ESCOLA": "472", "TV VERDES MARES  FORTALEZA": "484", "TV CAMARA": "470", "ZOOMOO": "6875", "SUPERMIX": "2695", "BANDNEWS HD": "242", "SHOPTIME": "414", "EPTV RIB.PRETO": "293", "VH1": "488", "Mundi Pop": "6641"}
    url = "http://www.sky.com.br/servicos/Guiadatv/rssGradeProgramacao.ashx?qChave=" + canais[canal.upper()]
    resultado = feedparser.parse(url)
    lista_canais = []
    cont = 0
    for c in resultado['entries']:
        data, nome = c['title'].split(' - ',1)
        hora2 = data[-5::]
        data2 = data[5:10]
        if data2 == dt and hora2 >= hr and cont < 4:
            lista_canais.append(u"%s | %s" % (hora2,nome))
            cont = cont + 1
    return lista_canais

def tempo(cidade):
    data = urllib2.urlopen('http://openweathermap.org/data/2.1/find/name?q=' + cidade)
    cities = load(data)
    resposta = []
    if cities['count'] > 0:
        city = cities['list'][0]
        resposta.append("Tempo em " + city[u'name'] + ": " + str(int(city[u'main'][u'temp'] - 273.15)) + u'C @ Min~Max: ' + str(int(city[u'main'][u'temp_min'] - 273.15)) + u'C~' + str(int(city[u'main'][u'temp_max'] - 273.15)) + u'C @ Populacao: ' + str(city[u'sys'][u'population']) + " @ Pressao: " + str(city[u'main'][u'pressure']) + "hPa @ Vento: " + str(city[u'wind'][u'speed']) + "m/s @ Humidade: " + str(city[u'main']['humidity']) + "%")
    else:
        resposta.append("Cidade nao encontrada: " + cidade)
    return resposta

class MinhaPrimeiraFabricaIRC(protocol.ReconnectingClientFactory):
    protocol = MeuPrimeiroProtocoloIRC
    canais = ['#filewarez','#overclock','#pootz','#torrents','#pootz.pre', '#cam4']
    admins = ['licensed']

if __name__ == '__main__':
    # roda o programa na tela mesmo
    reactor.connectTCP(HOST, PORT, MinhaPrimeiraFabricaIRC())
    # mostra o que está acontecendo em stdout:
    log.startLogging(sys.stdout)
    reactor.run()
    
    
elif __name__ == '__builtin__':
    application = service.Application('MeuPrimeiroProtocoloIRC')
    ircService = internet.TCPClient(HOST, PORT, MinhaPrimeiraFabricaIRC())
    ircService.setServiceParent(application)
