# Tablets, phones and VR

The cockpit view isn't tied to Starglance's window. Put it wherever it helps.

## A second monitor

Drag Starglance's window there. **Always on top** (tray menu, or **Settings → Agent → Window**) keeps it over the game, and **Hide the title bar** gives it the whole window. Or open `http://127.0.0.1:8740` in a browser on that screen.

## VR overlays

Overlay apps like **OVR Toolkit** and **XSOverlay** can show a window or a web page in VR. Point them at Starglance's window, or at:

```
http://127.0.0.1:8740/?compact=1
```

**Compact** is a narrow single column sized for an overlay, with its own layouts (**VR overlay**, **VR minimal**) that you can change like any other ([Customizing](/guide/customize)).

<img src="/shots/cockpit-compact.jpg" alt="The compact layout" style="max-width: 360px">

## A tablet or another PC at home

Starglance can show the cockpit view, and your fleet, to devices on your home network. It's **view only**: those devices can't change settings or reach the game.

1. **Settings → Agent → Other devices**: switch on **Show on other devices**.
2. Choose **Pair a device**.
3. On the tablet, open the address shown (like `http://192.168.1.20:8741`) and type the code, or scan the QR code.

Windows asks once whether Starglance may use your network: allow it on **private networks**.

- It's off until you switch it on, and only paired devices get in.
- You can remove a paired device at any time in the same place.
- It's plain HTTP, so use it on your home network, not on public Wi-Fi.

## Your phone, anywhere

For a phone, use your fleet's hub instead: it's https and works from anywhere. On the hub's fleet page, open **Your account → Sign in on another device**. It shows a short code; on the phone, open the hub's address, choose **I have a code** and type it. The code works once, for 10 minutes. See [The fleet page](/fleet/fleet-page#on-a-phone).

::: tip Keep the screen awake
**Settings → Dashboard → Keep the screen awake** stops a phone or tablet beside the game from going to sleep while the page is open. It needs an https page (your hub's) and, on iPhone and iPad, iOS 18.4 or later with the page added to the Home Screen.
:::
