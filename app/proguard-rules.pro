# Release hardening for kvsai. R8 removes unused code, renames implementation classes and
# folds constants. Android components referenced from the manifest are kept automatically.
-allowaccessmodification
-repackageclasses 'k'
-renamesourcefileattribute kvsai
-keepattributes RuntimeVisibleAnnotations,RuntimeInvisibleAnnotations,AnnotationDefault,Signature,InnerClasses,EnclosingMethod,SourceFile

# Keep enum contracts used by the UI/database while still allowing class-name obfuscation.
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
