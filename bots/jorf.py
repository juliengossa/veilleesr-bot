# MIT License
#
# Copyright (c) 2021 Julien Gossa
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

#!/usr/bin/env python

import urllib3
import os
import imgkit
import json
from io import StringIO
from datetime import datetime
import vbconfig

class JORF:
    def __init__(self, piste_client_id, piste_client_secret, wk_path):
        self.piste_client_id = piste_client_id
        self.piste_client_secret = piste_client_secret
        self.pm = urllib3.PoolManager()
        self.get_access_token()
        self.jorf = None
        self.sommaire = None
        self.esr = None

        self.css = os.path.dirname(os.path.abspath(__file__))+"/css/legifrance.css" #"jorf.css"
        self.wkoptions={"log-level":"info","javascript-delay":2000, "enable-local-file-access": ""}
        self.wkconfig = imgkit.config(wkhtmltoimage=wk_path)

    def get_access_token(self):
        if (self.piste_client_id is None or self.piste_client_secret is None):
            raise Exception("PISTE_CLIENT_ID and PISTE_CLIENT_SECRET env var must be configured.")

        req = self.pm.request(
            "POST",
            "https://oauth.piste.gouv.fr/api/oauth/token", #https://oauth.piste.gouv.fr/api/oauth/token/api/oauth/token
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'},
            body = "grant_type=client_credentials&client_id="+self.piste_client_id+"&client_secret="+self.piste_client_secret+"&scope=openid")
        self.access_token = json.loads(req.data)['access_token']
        return self.access_token

    def piste_req(self,controller,params):
        req = self.pm.request(
            "POST",
            "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/consult/"+controller,
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': 'Bearer '+self.access_token },
            body = json.dumps(params))
        return json.loads(req.data)

    @staticmethod
    def jorf2url(jorf):
        return "https://www.legifrance.gouv.fr/jorf" + jorf['idEli'][4:]

    @staticmethod
    def texte2url(texte):
        return "https://www.legifrance.gouv.fr/jorf/id/"+texte['id']

    def get_last_jorf(self):
        if self.jorf is None:
            self.jorf = self.piste_req("lastNJo",{"nbElement":1})
        return self.jorf

    def get_last_jorf_id(self):
        return self.get_last_jorf()['containers'][0]['id']


    def get_sommaire(self, since=None):
        self.since = since
        if self.sommaire is None:
            if since is None:
                resp = self.piste_req("jorfCont",{"id":self.get_last_jorf_id(), "pageNumber": 1, "pageSize": 100})
                self.sommaire = resp['items']
            else:
                self.sommaire = []
                resp = self.piste_req("jorfCont",{"start":since, "end":{'year': 2222, 'month': 1, 'dayOfMonth': 1}, "pageNumber": 1, "pageSize": 100})
                for jo in resp['items'][::-1][1:]:
                    joresp = self.piste_req("jorfCont",{"id":jo['joCont']['id'], "pageNumber": 1, "pageSize": 100})
                    self.sommaire += joresp['items']

        return self.sommaire


    @staticmethod
    def esr_detect(string, keywords=["echerche", "seignement supérieur", "niversité", "diplômes", "cole nationale", "coles nationales"]):
        return any([k in string for k in keywords])

    @staticmethod
    def esr_lookup(jorf):
        res = []
        #print('-' * jorf['niv'],  end = '')
        #print(jorf['titre'])
        if JORF.esr_detect(jorf['titre']): res += jorf['liensTxt']
        else:
            for txt in jorf['liensTxt']:
                if JORF.esr_detect(txt['titre']): res += [ txt ]
        for item in jorf['tms']:
            res += JORF.esr_lookup(item)
        return res

    def get_esr(self):
        if self.esr is None:
            self.esr = {}
            for jo in self.get_sommaire():
                self.esr[jo['joCont']['id']] = self.esr_lookup(jo['joCont']['structure']['tms'][0])
        return self.esr

    def get_text(self, id):
        return self.piste_req("jorf",{"textCid":id})

    def sommaire2html(self):
        html = '<div>'
        html += '<H1>Publications au Journal Officiel - Sélection ESR</H1>'
        for jo in self.get_sommaire():
            html += '<H2>'+jo['joCont']['titre']+"</H2>"
            html += "<ul>"
            esr = self.get_esr()[jo['joCont']['id']]
            if len(esr) == 0:
                html+='<H3 style="text-align:center;margin-top:1cm">Aucune publication concernant l\'ESR detectée.</H3>'
            else:
                for texte in self.get_esr()[jo['joCont']['id']]:
                    html += "<li>"+texte['titre']+"</li>"
                html += "</ul>"

        html += '</div>'
        return html

    @staticmethod
    def cont2html(cont):
        html = '<div>'
        html += "<H1>"+cont['title']+"</H1>"
        cont['articles'].sort(key=lambda x:int(x.get('num') if x.get('num') is not None else 0))
        for article in cont['articles']:
            if article['num'] is not None:
                html += "<H2>Article "+article['num']+"</H2>"
            html += article['content']
        html += '</div>'
        return html

    def html2img(self, html, id, write_img=False):
        head = '<!DOCTYPE html><html><head><meta charset="UTF-8"><link rel="stylesheet" href="'+self.css+'"></head>'
        tail = '</body></html>'

        fhtml = StringIO(head+html+tail)
        if write_img:
            imgkit.from_file(fhtml, id+'.jpeg', options=self.wkoptions, config=self.wkconfig)
            return id+'.jpeg'
        else:
            return {
                'filename':id+'.jpeg',
                'data':imgkit.from_file(fhtml, False, options=self.wkoptions, config=self.wkconfig),
                'content_type':"image/jpeg",
                'alt':"Contenu du texte n° "+id }
            # return BytesIO(imgkit.from_file(fhtml, False, options=self.wkoptions, config=self.wkconfig))

    def get_joposts(self, recap = False, write_img = False):
        sommaire = self.get_sommaire()
        if len(sommaire) == 0:
            return []

        jotext = "[#VeilleESR #JORFESR] Publications au Journal Officiel concernant l'#ESR\n\n"
        if recap:
            jotext += "\U0001F5DE Récapitulatif de la semaine du "+self.since['dayOfMonth']+"/"+self.since['month']+"/"+self.since['year']
        else:
            for jo in sommaire[0:2]:
                jotext += "\U0001F5DE #"+jo['joCont']['titre']+"\n"
            if len(sommaire) > 2:
                jotext += "..."
        joimg = self.html2img(self.sommaire2html(), 'header', write_img)

        url = self.jorf2url(sommaire[0]['joCont'])
        joposts = [ {'text':jotext, 'images':[ joimg ], 'cardurl': url,
            'card':{'url': url, 'title': jo['joCont']['titre'], 'description':"legifrance" } } ]

        esr = self.get_esr()
        for texte in sum([ esr[t] for t in esr], []):
            txt = texte['titre'] if len(texte['titre']) <= 200 else texte['titre'][:200]+"..."
            jotext = "[#JORF #JORFESR] "+txt+"\n\n\U0001F4F0 "

            cont = self.piste_req('jorf',{'textCid':texte['id']})
            html = self.cont2html(cont)
            joimg = self.html2img(html, texte['id'], write_img)

            url = self.texte2url(texte)
            joposts += [ {'text':jotext, 'images':[ joimg ], 'cardurl':url,
                'card':{'url': url, 'title': txt, 'description':"legifrance" } } ]

        return joposts


def main():
    config = vbconfig.Config.load()
    jorf = JORF(config.get("piste_client_id"),config.get("piste_client_secret"), config.get("wk_path"))

    jorf.get_sommaire(config.get('last_jorf'))
    #print(json.dumps(jorf.get_sommaire(),indent=2))
    print(jorf.get_joposts(write_img=True))

if __name__ == "__main__":
    main()
