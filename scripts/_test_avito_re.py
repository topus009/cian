import re

p = r"c:/Users/sj_89/Desktop/cian/data/avito_html/8013263223.html"
with open(p, encoding="utf-8", errors="replace") as f:
    t = f.read()

# After \"1280x960\":\" comes URL until \"
pat = r'\\"1280x960\\":\\"(https://.*?)(?=\\")'
urls = re.findall(pat, t)
print("count", len(urls))
for u in urls[:3]:
    print(u[:120])

want = "https://70.img.avito.st/image/1/1.6BCIjba5RPm-Osb01LbKe78tRv82LMbvviFG-zo4QPs.1Tklz-E56spnnQ4LW5q1v62srHa3_cV4yGd_x7PqBjQ"
if urls:
    u0 = urls[0]
    print("len", len(u0), len(want), "eq", u0 == want)
    print("tail u0", repr(u0[-8:]))
