// flutter-ship: release signing from the encrypted vault.
// `fastlane android release` decrypts the upload key into a temp folder and sets these
// variables for the build only. Without them (a plain `flutter run --release`) the debug
// key is used, and the release lane refuses to upload anything not signed by the upload key.
//
// In android/app/build.gradle.kts, inside `android { ... }`:

    signingConfigs {
        System.getenv("SHIP_KEYSTORE_PATH")?.let { path ->
            create("release") {
                storeFile = file(path)
                storePassword = System.getenv("SHIP_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("SHIP_KEY_ALIAS")
                keyPassword = System.getenv("SHIP_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }
