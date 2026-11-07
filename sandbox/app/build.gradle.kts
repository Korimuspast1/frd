import java.util.Properties

plugins {
    id("com.android.application")
}

val signingProps = Properties()
val signingPropsFile = rootProject.file("signing.properties")
if (signingPropsFile.exists()) {
    signingProps.load(signingPropsFile.inputStream())
}

android {
    namespace = "com.korimuspast.sandbox"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.korimuspast.sandbox"
        minSdk = 23
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        resourceConfigurations += listOf("ru", "en")
    }

    signingConfigs {
        create("release") {
            if (signingPropsFile.exists()) {
                storeFile = rootProject.file(signingProps.getProperty("KEYSTORE_FILE"))
                storePassword = signingProps.getProperty("KEYSTORE_PASSWORD")
                storeType = signingProps.getProperty("KEYSTORE_TYPE", "PKCS12")
                keyAlias = signingProps.getProperty("KEY_ALIAS")
                keyPassword = signingProps.getProperty("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
        }
        release {
            signingConfig = if (signingPropsFile.exists())
                signingConfigs.getByName("release")
            else
                signingConfigs.getByName("debug")
            isMinifyEnabled = false
            isShrinkResources = false
            isDebuggable = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }

    packaging {
        resources.excludes += setOf("META-INF/*.kotlin_module")
    }
}

androidComponents {
    onVariants { variant ->
        variant.outputs.forEach { output ->
            output.outputFileName.set(
                output.versionName.map { v -> "sandbox-${variant.name}-v$v.apk" }
            )
        }
    }
}

dependencies {
    // приложение использует только платформенные API Android
}
