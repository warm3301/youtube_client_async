## youtube_client_async - ассинхронная библиотека для парсинга youtube без API.

Аналогичные библиотеки pytube pytube-fix, yt-dlp:
 - pytube - имеет ограниченные возможности. Перестала поддеживаться. Синхронная библиотека
 - pytubefix - имеет совместимость с pytube, Вводятся новые функции. Синхронная библиотека
 - yt-dlp - как библиотека способна максимум на генерацию словаря, иное не документировано,
но способен парсить многие сайты помимо ютуба и имеет большой набор функций по загрузки видео из cli. Синхронная библиотека

Что позволяет делать youtube_client_async?
 - Получать информацию о видео, шортах, стримах, постах, каналах
 - Получать комментарии для видео, шортов, постов
 - Получать чат прямой трансляции
 - Получать видео, шорты, плейлисты, записи в "сообществе" на канале
 - Работать с субтитрами
 - Производить поиск по youtube
ассинхронность тут достигается благодоря aiohttp

### Пример загрузки
```
import asyncio
import youtube_client_async as yca
async main():
    url = ""
    async with yca.SessionRequest as sr:        # создаем сессию aiohttp. Этот класс - обёртка.
        it = yca.InnerTube(sr)                  # InnerTube - позволяет получить комментарии
        video = await yca.get_video(url, sr, it)
        print("title", video.title)
        print("lenght is seconds", video.lenght)

        streams = await video.get_streams()
        stream = streams.get_highest_resolution()
        downloaded = await yca.simple_download(stream,"res")
        print(f"{downloaded:.2f}")
        

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

### Загрузка с callback
```
import asyncio
import youtube_client_async as yca
import time


async def main():
    url = ""

    async with yca.SessionRequest() as sr:
        it = yca.InnerTube(sr,)
        pl = await yca.get_video(url,sr,it)
        print("title", pl.title)
        print("lenght is seconds", video.lenght)

        streams = await pl.get_streams()
        stream = streams.get_highest_resolution()



        downloaded_count_temp = 0
        current_download_speed = 0
        last_time = time.time()
        def show_message(response:bytes, downloaded, filesize:int):
            nonlocal downloaded_count_temp, current_download_speed, last_time
            downloaded_count_temp += len(response)
            percent = (downloaded / filesize) * 100
            print(
                (
                    f"\r{percent:.2f}% {current_download_speed:.2f}mb/sec "
                    f"{downloaded/1024/1024:.2f}mb "
                    f"from {filesize/1024/1024:.2f}mb  "
                ),
                end=""
            )
            if downloaded_count_temp > 1024 * 1024:
                current_download_speed = (downloaded_count_temp/1024/1024)/(time.time() - last_time)
                last_time = time.time()
                downloaded_count_temp = 0


        current_time = time.time()
        downloaded = await yca.simple_download(stream,"res",callback=show_message)
        
        time_delta = time.time() - current_time
        print(f"\n{time_delta:.2f} seconds")
        print(f"{(downloaded / 1024 / 1024) / time_delta:.2f} mb/sec")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```
