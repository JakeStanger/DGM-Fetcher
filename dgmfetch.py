import requests
import time

max_show = 2232
base_url = "https://www.dgmlive.com/tour-dates/"

if __name__ == '__main__':
    for i in range(1, max_show):
        print(i)
        r = requests.get(base_url + str(i))

        with open("html/" + str(i) + '.html', 'w') as f:
            f.write(r.text)

        time.sleep(2)
