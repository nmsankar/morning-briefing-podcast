from PIL import Image, ImageDraw, ImageFont
S=3000
img=Image.new("RGB",(S,S))
d=ImageDraw.Draw(img)
top,bot=(255,159,67),(28,40,92)
for y in range(S):
    t=y/S; d.line([(0,y),(S,y)],fill=tuple(int(top[i]*(1-t)+bot[i]*t) for i in range(3)))
d.ellipse([S//2-520,520,S//2+520,1560],fill=(255,214,120))
F="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def c(text,y,size,fill=(255,255,255)):
    f=ImageFont.truetype(F,size); w=d.textlength(text,font=f); d.text(((S-w)/2,y),text,font=f,fill=fill)
c("Mani's",1750,300); c("Morning Briefing",2080,300); c("Daily news · Markets · AI · Startups",2560,110,(230,230,240))
img.save("cover.jpg",quality=90)
